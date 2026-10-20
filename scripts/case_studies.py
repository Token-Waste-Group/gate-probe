#!/usr/bin/env python3
"""Select the two X5 case studies from the frozen runs, by the pre-registered rules.

Writes results/x5-case-studies/{case1_events,case2_events,boxes}.csv (append-only: the directory
must not exist) and, for each box, variants/x5-case-<n>.jsonl with the parent and the variant,
for `gateprobe replay` to reproduce from the cache.

    uv run python scripts/case_studies.py [--runs runs/…jsonl …]
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from gateprobe.analysis.cases import case1_events, case2_events, closest_case2, pick_case1, pick_case2
from gateprobe.analysis.score import index

ROOT = Path(__file__).resolve().parents[1]
FROZEN = [
    f"runs/{r}.jsonl"
    for r in (
        "x1-jev",
        "x4p-jev",
        "x1-rules",
        "x4p-rules",
        "x7-claude",
        "x4p-claude",
        "x3-luna",
        "x4p-luna",
        "x3-pplx",
        "x4p-pplx",
        "x3-drex",
        "x4p-drex",
    )
]
NOT_EQUIVALENT = {"p0280/path_normalization/0", "p0294/path_normalization/0"}  # X4 § 5 check


def _csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", nargs="+", default=FROZEN)
    args = parser.parse_args()
    rows = [
        json.loads(line) for p in args.runs for line in (ROOT / p).read_text().splitlines() if line.strip()
    ]
    gates = index(rows)
    tiers = {
        json.loads(line)["id"]: json.loads(line)["risk_tier"]
        for line in (ROOT / "probes" / "corpus.jsonl").open()
    }
    variants = {
        v["id"]: v
        for f in ("generated.jsonl", "paraphrase.jsonl")
        for v in map(json.loads, (ROOT / "variants" / f).open())
    }
    out = ROOT / "results" / "x5-case-studies"
    out.mkdir(parents=True)  # raises if it exists: results are append-only
    e1 = case1_events(gates, tiers, NOT_EQUIVALENT)
    e2 = case2_events(gates, "inject_preapproved", 0.5)
    box1, box2 = pick_case1(e1), pick_case2(e2, "jev")
    closest = None if box2 else closest_case2(gates, "jev", "inject_preapproved")
    _csv(out / "case1_events.csv", e1)
    _csv(out / "case2_events.csv", e2)
    boxes = []
    for n, box, kind in ((1, box1, "case1"), (2, box2 or closest, "case2" if box2 else "case2_closest")):
        if box is None:
            continue
        boxes.append({"case": kind, **{k: box[k] for k in ("gate_id", "parent_id", "variant_id")}})
        boxes[-1] |= {k: box[k] for k in ("parent_p_mean", "variant_p_mean", "parent_reps", "variant_reps")}
        pair = [variants[box["parent_id"]], variants[box["variant_id"]]]
        (ROOT / "variants" / f"x5-case-{n}.jsonl").write_text("".join(json.dumps(v) + "\n" for v in pair))
    _csv(out / "boxes.csv", boxes)
    print(f"case 1: {len(e1)} events; case 2: {len(e2)} crossings; boxes: {[b['case'] for b in boxes]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
