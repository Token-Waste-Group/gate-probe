"""The hand-labeled subset: a seeded, tier-stratified sample of probes, and the labels people give them.

Labels answer one question per probe: should this call be blocked under its
policy (deny) or not (allow)? They serve the calibration figure only, never
tuning generators, prompts or thresholds (docs/RELATIONS.md § 3.7). One
record per (probe, labeler) in probes/labels.jsonl; a probe's label is the
majority over its labelers, and a tie leaves it unlabeled.

Scope of v0: sampling (equal shares per risk tier, capped by what a tier
holds, the rest spread round-robin), reading and writing label records, the
majority vote. Out of scope: the labeling UI (scripts/label_cli.py).
"""

from __future__ import annotations

import datetime
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

from gateprobe.corpus.schema import LABELS, RISK_TIERS, Probe


def sample(probes: list[Probe], size: int = 60, seed: int = 13) -> list[Probe]:
    by_tier: dict[str, list[Probe]] = defaultdict(list)
    for p in sorted(probes, key=lambda p: p.id):
        by_tier[p.risk_tier].append(p)
    quota = {t: 0 for t in RISK_TIERS}
    remaining = size
    while remaining > 0:  # round-robin until the size is met or every tier is exhausted
        progressed = False
        for t in RISK_TIERS:
            if remaining and quota[t] < len(by_tier[t]):
                quota[t] += 1
                remaining -= 1
                progressed = True
        if not progressed:
            break
    rng = random.Random(seed)
    picked = [p for t in RISK_TIERS for p in rng.sample(by_tier[t], quota[t])]
    return sorted(picked, key=lambda p: p.id)


def append_label(path: Path, probe_id: str, label: str, labeler: str) -> None:
    if label not in LABELS:
        raise ValueError(f"label must be one of {LABELS}, got {label!r}")
    if not labeler.strip():
        raise ValueError("a labeler id is required")
    rec = {
        "probe_id": probe_id,
        "label": label,
        "labeler": labeler.strip(),
        "labeled_at": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")


def read_labels(path: Path) -> list[dict[str, str]]:
    if not Path(path).exists():
        return []
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def majority(records: list[dict[str, str]]) -> dict[str, str]:
    """probe id -> its majority label; the latest record per (probe, labeler) counts; ties are dropped."""
    latest: dict[tuple[str, str], str] = {}
    for r in records:
        latest[(r["probe_id"], r["labeler"])] = r["label"]
    votes: dict[str, Counter[str]] = defaultdict(Counter)
    for (pid, _), lab in latest.items():
        votes[pid][lab] += 1
    out = {}
    for pid, c in votes.items():
        top = c.most_common()
        if len(top) == 1 or top[0][1] > top[1][1]:
            out[pid] = top[0][0]
    return out
