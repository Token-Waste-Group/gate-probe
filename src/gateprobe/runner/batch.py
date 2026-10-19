"""Run a gate through the Anthropic Message Batches API (the Claude judge), into the same response cache.

Written from the claude-api skill's batches guide. Every (variant, repeat)
missing from the cache becomes one batch request whose `custom_id` is its
cache key (sha256 hex, 64 characters), so results land under exactly the key
the synchronous runner would use, repeat index included. A state file
(runs/<run_id>.batches.json) records every submitted batch, which batches are
collected, and which keys errored, so a rerun with the same run id resumes: it
never resubmits a pending key, re-collects a half-collected batch, and
resubmits only errored keys.

The $ cap is checked before anything is submitted: with no per-call cost
estimate (the X7 pilot sets `est_usd_per_call`), at most `pilot_limit`
requests may go out; with one, the projected cost of the missing requests
plus the run's recorded spend must fit under the cap. A refusal is cached as
its own outcome. Spend (at batch prices) is appended to the spend log.

Scope of v0: submit, poll, collect, resume, rows. Out of scope: cancelling batches.
"""

from __future__ import annotations

import csv
import json
import time
from collections.abc import Callable, Iterator
from dataclasses import asdict
from pathlib import Path
from typing import Any

from gateprobe.corpus.schema import Variant
from gateprobe.gates.base import GateRefusal
from gateprobe.gates.claude import ClaudeJudgeGate
from gateprobe.runner.cache import Cache, cache_key
from gateprobe.runner.run import ROOT, SPEND_FIELDS, CapReached, gate_request, git_hash, now


def _load_state(path: Path, run_id: str) -> dict[str, Any]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"run_id": run_id, "batches": [], "errored": [], "spent_usd": 0.0}


def _save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def run_batched(
    variants: list[Variant],
    gate: ClaudeJudgeGate,
    *,
    repeats: int,
    cache: Cache,
    run_id: str,
    cap_usd: float,
    config_digest: str,
    state_path: Path,
    est_usd_per_call: float | None = None,
    pilot_limit: int = 50,
    chunk: int = 10_000,
    poll_s: float = 60.0,
    sleep: Callable[[float], None] = time.sleep,
    spend_csv: Path | None = None,
    policies_dir: Path = ROOT / "policies",
) -> Iterator[dict[str, Any]]:
    state = _load_state(state_path, run_id)
    client = gate.client()
    work = []  # (variant, repeat, key, request)
    for v in variants:
        req = gate_request(v, policies_dir)
        for k in range(1, repeats + 1):
            work.append(
                (v, k, cache_key(gate.gate_id, gate.model_id, gate.mode, gate.request_bytes(req), k), req)
            )

    pending = {cid for b in state["batches"] if not b.get("collected") for cid in b["custom_ids"]}
    submitted = {cid for b in state["batches"] for cid in b["custom_ids"]}
    errored = set(state["errored"])
    missing = [
        w
        for w in work
        if cache.get(w[2]) is None and w[2] not in pending and (w[2] not in submitted or w[2] in errored)
    ]
    missing = list({w[2]: w for w in missing}.values())  # one request per key

    if missing:
        if est_usd_per_call is None:
            if len(missing) > pilot_limit:
                raise CapReached(
                    f"{gate.gate_id}: no est_usd_per_call yet; run a pilot of <= {pilot_limit} "
                    f"requests first (X7), not {len(missing)}"
                )
        elif state["spent_usd"] + len(missing) * est_usd_per_call > cap_usd:
            raise CapReached(
                f"{gate.gate_id}: {len(missing)} requests x ${est_usd_per_call:.5f} on top of "
                f"${state['spent_usd']:.4f} spent exceeds the ${cap_usd:.2f} cap"
            )
        for i in range(0, len(missing), chunk):
            part = missing[i : i + chunk]
            batch = client.messages.batches.create(
                requests=[{"custom_id": key, "params": gate.params(req)} for _, _, key, req in part]
            )
            ids = [key for _, _, key, _ in part]
            state["batches"].append(
                {"id": batch.id, "custom_ids": ids, "collected": False, "submitted_at": now()}
            )
            state["errored"] = sorted(set(state["errored"]) - set(ids))
            _save_state(state_path, state)

    fresh_calls = tokens_in = tokens_out = 0
    run_spent = 0.0  # this invocation's spend (the spend log); state["spent_usd"] is the run's total
    try:
        for b in state["batches"]:
            if b.get("collected"):
                continue
            while client.messages.batches.retrieve(b["id"]).processing_status != "ended":
                sleep(poll_s)
            names_for = {key: req.option_names for _, _, key, req in work}
            batch_spent = 0.0
            for result in client.messages.batches.results(b["id"]):
                key = result.custom_id
                if cache.get(key) is not None or key not in names_for:
                    continue  # already collected on an earlier, interrupted pass
                r = result.result
                if r.type != "succeeded":
                    state["errored"] = sorted(set(state["errored"]) | {key})
                    continue
                try:
                    d = gate.parse(r.message, names_for[key], latency_ms=0.0, batch=True)
                except GateRefusal as e:
                    cache.put(
                        key,
                        {
                            "refusal": e.details,
                            "message": str(e),
                            "created_at": now(),
                            "run_id": run_id,
                            "batch_id": b["id"],
                        },
                    )
                    continue
                except Exception as e:  # unparseable answers count as errors, never as verdicts
                    state["errored"] = sorted(set(state["errored"]) | {key})
                    state.setdefault("parse_errors", {})[key] = f"{type(e).__name__}: {e}"
                    continue
                cache.put(
                    key, {"decision": asdict(d), "created_at": now(), "run_id": run_id, "batch_id": b["id"]}
                )
                batch_spent += d.cost_usd
                fresh_calls += 1
                usage = d.raw.get("usage") or {}
                tokens_in += int(usage.get("input_tokens", 0) or 0)
                tokens_out += int(usage.get("output_tokens", 0) or 0)
            b["collected"] = True
            state["spent_usd"] += batch_spent
            run_spent += batch_spent
            _save_state(state_path, state)
    finally:
        if spend_csv is not None and fresh_calls:
            new = not spend_csv.exists()
            spend_csv.parent.mkdir(parents=True, exist_ok=True)
            with spend_csv.open("a", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=SPEND_FIELDS, lineterminator="\n")
                if new:
                    w.writeheader()
                w.writerow(
                    {
                        "run_id": run_id,
                        "gate_id": gate.gate_id,
                        "model_id": gate.model_id,
                        "calls": fresh_calls,
                        "input_tokens": tokens_in,
                        "output_tokens": tokens_out,
                        "usd": f"{run_spent:.6f}",
                        "ended_at": now(),
                    }
                )

    commit = git_hash()
    for v, k, key, _ in work:
        row: dict[str, Any] = {
            "run_id": run_id,
            "variant_id": v.id,
            "probe_id": v.probe_id,
            "parent_id": v.parent_id,
            "relation_class": v.relation_class,
            "transform": v.transform,
            "repeat": k,
            "gate_id": gate.gate_id,
            "model_id": gate.model_id,
            "mode": gate.mode,
            "git_hash": commit,
            "config_hash": config_digest,
            "cache_key": key,
            "batch": True,
        }
        entry = cache.get(key)
        if entry is None:
            yield {
                **row,
                "status": "error",
                "error": "no batch result (errored, expired or canceled)",
                "timestamp": now(),
            }
        elif "refusal" in entry:
            yield {**row, "status": "refusal", "error": entry.get("message", ""), "timestamp": now()}
        else:
            d = entry["decision"]
            yield {
                **row,
                "status": "ok",
                "cached": entry.get("run_id") != run_id,
                "verdict": d["verdict"],
                "p_block": d["p_block"],
                "latency_ms": d["latency_ms"],
                "cost_usd": d["cost_usd"],
                "served_model": (d.get("raw") or {}).get("model"),
                "timestamp": now(),
            }
