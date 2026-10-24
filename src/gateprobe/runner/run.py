"""Run variants x repeats through one gate: cache first, then the gate with retries, under the $ cap.

Scope of v0: `run_gate` yields one row per (variant, repeat) with full
provenance (git hash, config hash, gate, pinned model, repeat, timestamp);
`replay=True` serves only from the cache and fails on a miss, so it needs no
key (with `allow_misses`, a miss becomes a `replay_miss` row instead: a call
the recorded run never got an answer for, such as an HTTP error); the
per-gate $ cap is checked before every call; retryable errors back off
exponentially; spend is appended to `spend_csv` (the CLI passes
results/spend.csv) when the run ends, however it ends. Out of scope: analysis
(R6) and Message Batches (R8).
"""

from __future__ import annotations

import csv
import datetime
import hashlib
import json
import os
import subprocess
import time
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path
from typing import Any

from gateprobe.corpus.render import FILES
from gateprobe.corpus.schema import Variant
from gateprobe.gates.base import GateAdapter, GateDecision, GateRefusal, GateRequest, ToolCall
from gateprobe.runner.cache import Cache, cache_key

ROOT = Path(__file__).resolve().parents[3]
SPEND_FIELDS = ["run_id", "gate_id", "model_id", "calls", "input_tokens", "output_tokens", "usd", "ended_at"]


class ReplayMiss(LookupError):
    """--replay found no cached answer for a call: the replay bundle is incomplete."""


class CapReached(RuntimeError):
    """The next call would take this run's spend past the gate's $ cap."""


def git_hash(root: Path = ROOT) -> str:
    """The commit the code runs from (+ "-dirty"). Without git (the Docker image), the commit baked
    in at build time (GATEPROBE_GIT_HASH), else "unknown"; provenance never crashes a run."""
    try:
        r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True)
        sha = r.stdout.strip()
        if sha:
            dirty = subprocess.run(
                ["git", "status", "--porcelain", "--untracked-files=no"],
                cwd=root,
                capture_output=True,
                text=True,
            ).stdout.strip()
            return sha + ("-dirty" if dirty else "")
    except OSError:
        pass
    return os.environ.get("GATEPROBE_GIT_HASH") or "unknown"


def config_hash(*configs: Any) -> str:
    blob = json.dumps(configs, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def now() -> str:
    return datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def gate_request(variant: Variant, policies_dir: Path = ROOT / "policies") -> GateRequest:
    policy = variant.policy_text
    if policy is None:
        policy = (policies_dir / variant.policy_id / FILES[variant.policy_rendering]).read_text(
            encoding="utf-8"
        )
    return GateRequest(
        policy=policy,
        call=ToolCall(variant.tool, variant.call),
        context=variant.context,
        option_names=variant.option_names,
        policy_id=variant.policy_id,
    )


def _usage_tokens(raw: dict[str, Any]) -> tuple[int, int]:
    usage = raw.get("usage") or {}
    return int(usage.get("input_tokens", 0) or 0), int(usage.get("output_tokens", 0) or 0)


def _put(cache: Cache, key: str, entry: dict[str, Any]) -> dict[str, Any]:
    """Store an answer; if an identical request already stored one (a concurrent duplicate), keep that."""
    try:
        cache.put(key, entry)
        return entry
    except FileExistsError:
        return cache.get(key) or entry


def _call_with_retries(
    gate: GateAdapter, request: GateRequest, retry: dict[str, float], sleep: Callable[[float], None]
) -> GateDecision:
    attempts = int(retry.get("max_attempts", 5))
    delay, cap = float(retry.get("backoff_initial_s", 1.0)), float(retry.get("backoff_max_s", 60.0))
    for attempt in range(1, attempts + 1):
        try:
            return gate.decide(request)
        except Exception as e:
            if not getattr(e, "retryable", False) or attempt == attempts:
                raise
            sleep(min(delay * 2 ** (attempt - 1), cap))
    raise AssertionError("unreachable")


def run_gate(
    variants: list[Variant],
    gate: GateAdapter,
    *,
    repeats: int,
    cache: Cache,
    run_id: str,
    cap_usd: float,
    config_digest: str,
    replay: bool = False,
    allow_misses: bool = False,
    retry: dict[str, float] | None = None,
    spend_csv: Path | None = None,
    policies_dir: Path = ROOT / "policies",
    sleep: Callable[[float], None] = time.sleep,
    workers: int = 1,
) -> Iterator[dict[str, Any]]:
    """Rows in variant x repeat order. With `workers` > 1, calls run in parallel chunks of that
    size; the cap is checked before each chunk against the chunk's projected cost, and the rows
    come out in the same order as a sequential run."""
    mode = getattr(gate, "mode", "")
    commit = git_hash()
    spent, fresh_calls, tokens_in, tokens_out = 0.0, 0, 0, 0
    tasks: list[tuple[Variant, GateRequest, int]] = []
    for variant in variants:
        request = gate_request(variant, policies_dir)
        tasks.extend((variant, request, k) for k in range(1, repeats + 1))

    def one(task: tuple[Variant, GateRequest, int]) -> tuple[dict[str, Any], dict[str, Any] | None]:
        """(row, {cost_usd, raw} if a billed call was made: an answer or a refusal).
        Thread-safe: the cache is per-key and exclusive."""
        variant, request, k = task
        row: dict[str, Any] = {
            "run_id": run_id,
            "variant_id": variant.id,
            "probe_id": variant.probe_id,
            "parent_id": variant.parent_id,
            "relation_class": variant.relation_class,
            "transform": variant.transform,
            "repeat": k,
            "gate_id": gate.gate_id,
            "model_id": gate.model_id,
            "mode": mode,
            "git_hash": commit,
            "config_hash": config_digest,
        }
        try:
            request_bytes = gate.request_bytes(request)
        except Exception as e:  # e.g. NotApplicable: option names this mode can't express
            return {**row, "status": "not_applicable", "error": str(e), "timestamp": now()}, None
        key = cache_key(gate.gate_id, gate.model_id, mode, request_bytes, k)
        row["cache_key"] = key
        entry = cache.get(key)
        cached, fresh = entry is not None, None
        if not cached:
            if replay:
                miss = f"no cached answer for {variant.id} repeat {k} on {gate.gate_id}"
                if not allow_misses:
                    raise ReplayMiss(miss)
                return {**row, "status": "replay_miss", "error": miss, "timestamp": now()}, None
            try:
                decision = _call_with_retries(gate, request, retry or {}, sleep)
            except GateRefusal as e:  # its own outcome: cached, reported, never re-asked elsewhere
                _put(
                    cache,
                    key,
                    {"refusal": e.details, "message": str(e), "created_at": now(), "run_id": run_id},
                )
                billed = {  # a refusal is still billed
                    "cost_usd": float(e.details.get("cost_usd", 0.0) or 0.0),
                    "raw": {"usage": e.details.get("usage") or {}},
                }
                return {
                    **row,
                    "status": "refusal",
                    "cached": False,
                    "error": str(e),
                    "timestamp": now(),
                }, billed
            except Exception as e:
                return {
                    **row,
                    "status": "error",
                    "error": f"{type(e).__name__}: {e}",
                    "timestamp": now(),
                }, None
            entry = _put(cache, key, {"decision": asdict(decision), "created_at": now(), "run_id": run_id})
            fresh = {"cost_usd": decision.cost_usd, "raw": decision.raw}
        if "refusal" in entry:
            return {
                **row,
                "status": "refusal",
                "cached": cached,
                "error": entry.get("message", ""),
                "timestamp": now(),
            }, None
        d = entry["decision"]
        return {
            **row,
            "status": "ok",
            "cached": cached,
            "verdict": d["verdict"],
            "p_block": d["p_block"],
            "latency_ms": d["latency_ms"],
            "cost_usd": d["cost_usd"],
            "served_model": (d.get("raw") or {}).get("model"),
            "timestamp": now(),
        }, fresh

    pool = ThreadPoolExecutor(max_workers=workers) if workers > 1 else None
    try:
        size = max(1, workers)
        for i in range(0, len(tasks), size):
            chunk = tasks[i : i + size]
            projected = (spent / fresh_calls if fresh_calls else 0.0) * len(chunk)
            if spent + projected > cap_usd:
                raise CapReached(f"{gate.gate_id}: spent ${spent:.4f} of a ${cap_usd:.2f} cap")
            results = pool.map(one, chunk) if pool else map(one, chunk)
            for row, fresh in results:
                if fresh is not None:  # a billed call: an answer or a refusal
                    spent += fresh["cost_usd"]
                    fresh_calls += 1
                    t_in, t_out = _usage_tokens(fresh["raw"])
                    tokens_in, tokens_out = tokens_in + t_in, tokens_out + t_out
                yield row
    finally:
        if pool:
            pool.shutdown(wait=True, cancel_futures=True)
        if spend_csv is not None and fresh_calls:
            spend_csv.parent.mkdir(parents=True, exist_ok=True)
            new = not spend_csv.exists()
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
                        "usd": f"{spent:.6f}",
                        "ended_at": now(),
                    }
                )
