#!/usr/bin/env python3
"""Distill the frozen replay bundle into the Space's data.json (I8).

The Space is a static page: it never calls a gate, and every answer it shows was recorded in the
frozen runs. This script reads those runs from the bundle archive (scripts/build_bundle.py), the
variants and policies the gates saw (what gateprobe's runner sends, via `gate_request`), and the
frozen tables in results/x4-final/, and writes one deterministic JSON file:

- meta: the bundle's name and sha256, the freeze commit, the row count;
- gates, floors, classes (relations.csv) and transforms (transforms.csv), with their intervals;
- flips: every (gate, parent, variant) pair whose verdicts differ at some repeat where both sides
  answered (refusals don't count), with verdict and p_block per repeat on both sides and the
  direction: `looser` (deny -> allow at some repeat), `stricter`, or `both`;
- inputs and policies: what the gate was asked, for both sides of every flip.

    uv run python integrations/hf-space/build_data.py --bundle dist/gateprobe-replay-19fd14a.tar.gz

Scope of v0: flips only (a pair that never flips isn't listed; the tables give its rates).
Out of scope: publishing the Space (H5).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import tarfile
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
GATES = {
    "jev": "Jev 1.14",
    "gpt-6-luna-decisions": "GPT-6 Luna Decisions",
    "pplx-decider": "pplx-decider v1.2",
    "drex": "drex v1.5",
    "judge-claude": "Claude Opus 5.5 judge",
    "rules": "Rule set",
}
CLASS_FIELDS = ("n_pairs", "rate", "rate_lo", "rate_hi", "excess", "excess_lo", "excess_hi")
VARIANT_FILES = ("variants/generated.jsonl", "variants/paraphrase.jsonl")


def _num(x: str) -> float | int | None:
    if x in ("", None):
        return None
    v = float(x)
    return int(v) if v.is_integer() and "." not in x else round(v, 6)


def _csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def read_bundle(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """(BUNDLE.json, every row of the frozen runs it lists), read straight from the archive."""
    with tarfile.open(path) as tar:
        names = {Path(m.name).relative_to(Path(m.name).parts[0]).as_posix(): m for m in tar.getmembers()}
        meta = json.load(tar.extractfile(names["BUNDLE.json"]))
        rows = [
            json.loads(line)
            for run in meta["runs"]
            for line in tar.extractfile(names[f"runs/{run}.jsonl"]).read().decode("utf-8").splitlines()
            if line.strip()
        ]
    return meta, rows


def flips(rows: list[dict[str, Any]], parents: dict[str, str | None]) -> list[dict[str, Any]]:
    answers: dict[tuple[str, str], dict[int, list]] = defaultdict(dict)
    info: dict[tuple[str, str], dict[str, Any]] = {}
    for r in rows:
        if r["status"] == "ok":
            key = (r["gate_id"], r["variant_id"])
            answers[key][r["repeat"]] = [r["verdict"], r["p_block"]]
            info[key] = r
    out = []
    for (gate, vid), reps in sorted(answers.items()):
        parent = parents.get(vid)
        if parent is None or (gate, parent) not in answers:
            continue
        before = answers[(gate, parent)]
        shared = sorted(set(before) & set(reps))
        looser = any(before[k][0] == "deny" and reps[k][0] == "allow" for k in shared)
        stricter = any(before[k][0] == "allow" and reps[k][0] == "deny" for k in shared)
        if not (looser or stricter):
            continue
        r = info[(gate, vid)]
        out.append(
            {
                "gate": gate,
                "class": r["relation_class"],
                "transform": r["transform"],
                "parent": parent,
                "variant": vid,
                "repeats": shared,
                "before": [before[k] for k in shared],
                "after": [reps[k] for k in shared],
                "direction": "both" if looser and stricter else "looser" if looser else "stricter",
            }
        )
    return out


def inputs(ids: set[str], root: Path) -> tuple[dict[str, Any], dict[str, dict[str, str]]]:
    """What the gate saw for each id: the request gateprobe's runner builds (gate_request)."""
    from gateprobe.corpus.schema import DEFAULT_OPTION_NAMES, Variant, load_jsonl
    from gateprobe.runner.run import gate_request

    out: dict[str, Any] = {}
    policies: dict[str, dict[str, str]] = defaultdict(dict)
    for src in VARIANT_FILES:
        for v in load_jsonl(root / src, Variant):
            if v.id not in ids:
                continue
            req = gate_request(v, root / "policies")
            item: dict[str, Any] = {"tool": v.tool, "call": v.call, "policy": v.policy_id}
            if v.policy_text is None:
                item["rendering"] = v.policy_rendering
                policies[v.policy_id][v.policy_rendering] = req.policy
            else:  # a P policy rewording: the gate saw this text, not a rendering file
                item["policy_text"] = req.policy
            if v.context:
                item["context"] = v.context
            if v.option_names != DEFAULT_OPTION_NAMES:
                item["options"] = v.option_names
            out[v.id] = item
    missing = sorted(ids - set(out))
    if missing:
        raise SystemExit(f"{len(missing)} flip ids missing from the variant files, e.g. {missing[0]}")
    return out, dict(policies)


def build(bundle: Path, root: Path = ROOT) -> dict[str, Any]:
    from gateprobe.corpus.schema import Variant, load_jsonl

    meta, rows = read_bundle(bundle)
    parents = {v.id: v.parent_id for src in VARIANT_FILES for v in load_jsonl(root / src, Variant)}
    flipped = flips(rows, parents)
    given, policies = inputs({f[k] for f in flipped for k in ("parent", "variant")}, root)
    results = root / "results" / "x4-final"
    keep = ("gate_id", "class", "transform", "label", "rate_kind")

    def table(name: str) -> list[dict[str, Any]]:
        return [
            {
                **{k: r[k] for k in keep if k in r},
                "bonferroni": r.get("positive_bonferroni") == "True",
                **{k: _num(r[k]) for k in CLASS_FIELDS},
            }
            for r in _csv(results / name)
        ]

    return {
        "meta": {
            "bundle": meta["bundle"],
            "bundle_sha256": hashlib.sha256(bundle.read_bytes()).hexdigest(),
            "results_frozen_at": meta["results_frozen_at"],
            "rows": len(rows),
            "repeats": max(r["repeat"] for r in rows),
        },
        "gates": [{"id": g, "name": n} for g, n in GATES.items()],
        "floors": {
            r["gate_id"]: {k: _num(r[k]) for k in ("n_items", "f", "f_lo", "f_hi", "delta")}
            for r in _csv(results / "floor.csv")
        },
        "classes": table("relations.csv"),
        "transforms": table("transforms.csv"),
        "flips": flipped,
        "inputs": given,
        "policies": policies,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--bundle", type=Path, required=True, help="the replay bundle archive (.tar.gz)")
    parser.add_argument("--out", type=Path, default=Path(__file__).with_name("data.json"))
    args = parser.parse_args()
    data = build(args.bundle)
    args.out.write_text(json.dumps(data, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"{len(data['flips'])} flips, {len(data['inputs'])} inputs -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
