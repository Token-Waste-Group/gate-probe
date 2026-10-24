#!/usr/bin/env python3
"""Build probes/corpus.jsonl from configs/corpus.yaml and refresh the counts in docs/CORPUS.md.

Deterministic (seeded): rerunning it on the same config reproduces both files
byte for byte, which tests/test_corpus.py checks.

    uv run python scripts/build_corpus.py [--config configs/corpus.yaml]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from gateprobe.corpus.build import build, counts_markdown, load_config, splice_counts, to_jsonl

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", type=Path, default=ROOT / "configs" / "corpus.yaml")
    parser.add_argument("--out", type=Path, default=ROOT / "probes" / "corpus.jsonl")
    parser.add_argument("--datasheet", type=Path, default=ROOT / "docs" / "CORPUS.md")
    args = parser.parse_args()

    probes = build(load_config(args.config))
    args.out.write_text(to_jsonl(probes), encoding="utf-8")
    sheet = args.datasheet.read_text(encoding="utf-8")
    args.datasheet.write_text(splice_counts(sheet, counts_markdown(probes)), encoding="utf-8")
    print(
        f"{len(probes)} probes -> {args.out.relative_to(ROOT)}; counts -> {args.datasheet.relative_to(ROOT)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
