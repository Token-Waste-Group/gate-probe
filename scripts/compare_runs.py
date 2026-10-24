#!/usr/bin/env python3
"""Check that replayed runs reproduce the frozen ones: the same answer per (gate, variant, repeat).

An answer is (status, verdict, p_block). A frozen `error` row and a replayed `replay_miss` row
agree (no answer either way). Only rows present in both sets are compared; the counts say how
many were.

    uv run python scripts/compare_runs.py --frozen runs/x3-drex.jsonl --replayed runs/replay-drex.jsonl

Exit 0 when every shared row agrees and at least one row was compared, else 1.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

Key = tuple[str, str, int]


def answers(paths: list[Path]) -> dict[Key, tuple]:
    out = {}
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            status = "no_answer" if r["status"] in ("error", "replay_miss") else r["status"]
            out[(r["gate_id"], r["variant_id"], r["repeat"])] = (status, r.get("verdict"), r.get("p_block"))
    return out


def compare(frozen: dict[Key, tuple], replayed: dict[Key, tuple]) -> tuple[int, list[Key]]:
    shared = sorted(set(frozen) & set(replayed))
    return len(shared), [k for k in shared if frozen[k] != replayed[k]]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--frozen", nargs="+", required=True, type=Path)
    parser.add_argument("--replayed", nargs="+", required=True, type=Path)
    args = parser.parse_args()
    frozen, replayed = answers(args.frozen), answers(args.replayed)
    n, diff = compare(frozen, replayed)
    print(f"{n} rows compared ({len(replayed)} replayed, {len(frozen)} frozen): {len(diff)} differ")
    for k in diff[:10]:
        print(f"  {k}: frozen {frozen[k]} replayed {replayed[k]}")
    return 0 if n and not diff else 1


if __name__ == "__main__":
    sys.exit(main())
