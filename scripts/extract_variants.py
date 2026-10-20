#!/usr/bin/env python3
"""Copy named variants (by id, in the order given) from the variant files into a small JSONL,
for `gateprobe replay` to reproduce single cases from the cache (X5, the video).

    uv run python scripts/extract_variants.py variants/x5-alt-1e.jsonl p0109/base p0109/policy_format/0
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ("variants/generated.jsonl", "variants/paraphrase.jsonl")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out", type=Path)
    parser.add_argument("ids", nargs="+")
    args = parser.parse_args()
    by_id = {v["id"]: v for src in SOURCES for v in map(json.loads, (ROOT / src).open(encoding="utf-8"))}
    missing = [i for i in args.ids if i not in by_id]
    if missing:
        raise SystemExit(f"unknown variant ids: {missing}")
    args.out.write_text("".join(json.dumps(by_id[i]) + "\n" for i in args.ids), encoding="utf-8")
    print(f"{len(args.ids)} variants -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
