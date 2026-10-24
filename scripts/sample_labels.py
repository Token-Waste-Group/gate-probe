#!/usr/bin/env python3
"""Draw the hand-labeled subset (C7): a seeded, tier-stratified sample of 60 probes,
written to probes/label_sample.jsonl.

Deterministic: the same corpus and seed always give the same sample, which
tests/test_labels.py checks against the committed file.

    uv run python scripts/sample_labels.py [--size 60] [--seed 13]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from gateprobe.corpus.labels import sample
from gateprobe.corpus.schema import Probe, load_jsonl

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--size", type=int, default=60)
    parser.add_argument("--seed", type=int, default=13)
    args = parser.parse_args()
    picked = sample(load_jsonl(ROOT / "probes" / "corpus.jsonl", Probe), args.size, args.seed)
    out = ROOT / "probes" / "label_sample.jsonl"
    out.write_text(
        "".join(json.dumps({"probe_id": p.id, "risk_tier": p.risk_tier}) + "\n" for p in picked),
        encoding="utf-8",
    )
    print(f"{len(picked)} probes -> {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
