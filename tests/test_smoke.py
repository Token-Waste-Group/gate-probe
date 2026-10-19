"""Smoke tests: the package imports and the plan ledger is machine-parseable.

Scope of v0: guard the autonomous-loop plumbing (the docs/PLAN.md format that
scripts/claim.py and scripts/mark.py depend on). Out of scope: tool logic.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FIELDS = {"status", "owner", "claimed_at", "deps", "source", "done-when"}
# "cut" is a terminal status for a step retired by human decision (e.g. a
# [STRETCH] step after a reduced-scope G2): like "done" it is finished and never
# re-claimed, but it did not satisfy its done-when.
VALID_BASE_STATUSES = {"todo", "claimed", "in_review", "done", "blocked", "cut"}
KNOWN_TAGS = {"API", "GPU", "GATE", "HUMAN", "STRETCH"}
KNOWN_LANES = {"E", "S", "C", "R", "X", "I", "W", "G", "H"}


def _load_claim_module():
    spec = importlib.util.spec_from_file_location("claim", ROOT / "scripts" / "claim.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["claim"] = mod
    spec.loader.exec_module(mod)
    return mod


def _plan_blocks():
    claim = _load_claim_module()
    lines = (ROOT / "docs" / "PLAN.md").read_text(encoding="utf-8").splitlines()
    return claim, claim.parse(lines)


def test_package_imports():
    import gateprobe

    assert gateprobe.__version__


def test_plan_ledger_parses_and_is_consistent():
    claim, blocks = _plan_blocks()
    assert blocks, "docs/PLAN.md has no step blocks"

    ids = [b["id"] for b in blocks]
    assert len(ids) == len(set(ids)), "duplicate step ids in docs/PLAN.md"

    id_set = set(ids)
    for b in blocks:
        missing = REQUIRED_FIELDS - set(b["fields"])
        assert not missing, f"step {b['id']} missing fields: {missing}"
        status = claim.base_status(b)
        assert status in VALID_BASE_STATUSES, f"step {b['id']} has odd status {claim.status_of(b)!r}"
        for dep in claim.deps_of(b):
            assert dep in id_set, f"step {b['id']} depends on unknown step {dep!r}"


def test_plan_tags_and_lanes_are_known_and_consistent():
    claim, blocks = _plan_blocks()
    for b in blocks:
        tags = claim.tags_of(b)
        assert tags <= KNOWN_TAGS, f"step {b['id']} has unknown tags {tags - KNOWN_TAGS}"
        lane = claim.lane_of(b)
        assert lane in KNOWN_LANES, f"step {b['id']} is in unknown lane {lane!r}"
        # the lane letter and the tag must agree, so `--lane G` / HUMAN-skipping stay meaningful
        assert ("GATE" in tags) == (lane == "G"), f"step {b['id']}: [GATE] steps and lane G must coincide"
        assert ("HUMAN" in tags) == (lane == "H"), f"step {b['id']}: [HUMAN] steps and lane H must coincide"


def test_plan_has_no_dependency_cycles():
    claim, blocks = _plan_blocks()
    deps = {b["id"]: claim.deps_of(b) for b in blocks}
    state: dict[str, int] = {}  # 1 = on the current path, 2 = finished

    def visit(node: str, path: list[str]) -> None:
        if state.get(node) == 2:
            return
        assert state.get(node) != 1, f"dependency cycle: {' -> '.join(path)}"
        state[node] = 1
        for d in deps.get(node, []):
            visit(d, [*path, d])
        state[node] = 2

    for node in deps:
        visit(node, [node])


def test_plan_has_a_frontier_or_is_human_gated():
    """The ledger must never truly deadlock. A healthy frontier is: an eligible
    todo (an agent's or a human's), something in flight (claimed/in_review), or
    a blocked step a human can unblock. A *real* deadlock is only when
    unfinished todo steps remain but none is eligible, nothing is in flight, and
    nothing is blocked — work is stuck with no human-resolvable path. A
    legitimate pause waiting on human input is not a deadlock."""
    claim, blocks = _plan_blocks()
    statuses = [claim.base_status(b) for b in blocks]
    if all(s in {"done", "cut"} for s in statuses):  # every step finished or retired
        return
    in_flight = any(s in {"claimed", "in_review"} for s in statuses)
    human_gated = any(s == "blocked" for s in statuses)
    assert claim.eligible(blocks) or in_flight or human_gated, (
        "docs/PLAN.md is deadlocked: unfinished todo steps but none eligible, "
        "nothing in flight, and nothing blocked for a human to unblock"
    )
