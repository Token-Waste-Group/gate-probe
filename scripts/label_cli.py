#!/usr/bin/env python3
"""Label the sampled probes in the terminal (H2): shows each call with its policy, records allow/deny.

Each answer is appended to probes/labels.jsonl with your labeler id; probes you
already labeled are skipped, so you can stop and resume. Read docs/LABELING.md
first.

    uv run python scripts/label_cli.py --labeler <your-id>

Keys: a = allow, d = deny, s = skip for now, q = quit.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path

from gateprobe.corpus.labels import append_label, read_labels
from gateprobe.corpus.render import FILES
from gateprobe.corpus.schema import Probe, load_jsonl

ROOT = Path(__file__).resolve().parents[1]
KEYS = {"a": "allow", "d": "deny"}


def run(labeler: str, root: Path = ROOT, ask: Callable[[str], str] = input, out=sys.stdout) -> int:
    probes = {p.id: p for p in load_jsonl(root / "probes" / "corpus.jsonl", Probe)}
    sample = [
        json.loads(line)["probe_id"]
        for line in (root / "probes" / "label_sample.jsonl").read_text().splitlines()
        if line.strip()
    ]
    labels_path = root / "probes" / "labels.jsonl"
    done = {r["probe_id"] for r in read_labels(labels_path) if r["labeler"] == labeler}
    todo = [pid for pid in sample if pid not in done]
    print(f"{len(done)} labeled, {len(todo)} to go. a = allow, d = deny, s = skip, q = quit.", file=out)
    count = 0
    for i, pid in enumerate(todo, start=1):
        p = probes[pid]
        policy = (root / "policies" / p.policy_id / FILES["prose"]).read_text(encoding="utf-8").strip()
        call = p.call.get("command") if "command" in p.call else json.dumps(p.call, ensure_ascii=False)
        print(f"\n[{i}/{len(todo)}] {pid} · policy {p.policy_id}\n{policy}\n\n  {p.tool}: {call}", file=out)
        while True:
            key = ask("Block it (d) or allow it (a)? ").strip().lower()
            if key in KEYS:
                append_label(labels_path, pid, KEYS[key], labeler)
                count += 1
                break
            if key == "s":
                break
            if key == "q":
                print(f"saved {count} labels", file=out)
                return 0
    print(f"saved {count} labels; done", file=out)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--labeler", required=True, help="your labeler id, e.g. your initials")
    return run(parser.parse_args().labeler)


if __name__ == "__main__":
    raise SystemExit(main())
