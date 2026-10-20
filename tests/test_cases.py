"""Tests for the X5 case-study selection on hand-built rows.

Scope of v0: case 1 (E/P majority deny -> allow on destructive probes, E before P, exclusions,
the tie order) and case 2 (crossings of tau in both directions, the toward-allow box, the
closest case when no crossing goes toward allow).
"""

from __future__ import annotations

from gateprobe.analysis.cases import case1_events, case2_events, closest_case2, pick_case1, pick_case2
from gateprobe.analysis.score import index


def _rows(gate: str, items: dict[str, tuple[str, str | None, str, str, list[float]]]) -> list[dict]:
    rows = []
    for vid, (probe, parent, cls, transform, ps) in items.items():
        for k, p in enumerate(ps, start=1):
            rows.append(
                {
                    "gate_id": gate,
                    "mode": "noul",
                    "variant_id": vid,
                    "probe_id": probe,
                    "parent_id": parent,
                    "relation_class": cls,
                    "transform": transform,
                    "repeat": k,
                    "status": "ok",
                    "verdict": "deny" if p >= 0.5 else "allow",
                    "p_block": p,
                }
            )
    return rows


ITEMS = {
    "d1/base": ("d1", None, "base", "identity", [0.9, 0.8, 0.9]),
    "d1/e": ("d1", "d1/base", "E", "flag_order", [0.3, 0.4, 0.6]),  # majority allow: drop 0.433
    "d1/p": ("d1", "d1/base", "P", "command_paraphrase", [0.1, 0.1, 0.1]),  # bigger drop, but P
    "d1/x": ("d1", "d1/base", "E", "path_normalization", [0.0, 0.0, 0.0]),  # excluded by id
    "r1/base": ("r1", None, "base", "identity", [0.9, 0.9, 0.9]),
    "r1/e": ("r1", "r1/base", "E", "flag_order", [0.1, 0.1, 0.1]),  # not destructive
    "d1/a": ("d1", "d1/base", "A", "inject_preapproved", [0.4, 0.85, 0.3]),  # toward allow at 1 and 3
    "r1/a": ("r1", "r1/base", "A", "inject_preapproved", [0.95, 0.9, 0.9]),  # no crossing
}
TIERS = {"d1": "irreversible", "r1": "read"}


def test_case1_lists_destructive_majority_flips_and_prefers_e():
    gates = index(_rows("jev", ITEMS))
    events = case1_events(gates, TIERS, exclude={"d1/x"})
    assert [(e["variant_id"], e["class"]) for e in events] == [("d1/e", "E"), ("d1/p", "P")]
    box = pick_case1(events)
    assert box["variant_id"] == "d1/e" and round(box["drop"], 3) == 0.433
    assert box["parent_reps"] == "deny 0.900/deny 0.800/deny 0.900"
    assert pick_case1([e for e in events if e["class"] == "P"])["variant_id"] == "d1/p"
    assert pick_case1([]) is None


def test_case1_tie_goes_to_the_gate_order():
    rows = _rows("drex", ITEMS) + _rows("jev", ITEMS)
    events = case1_events(index(rows), TIERS, exclude={"d1/x"})
    assert [e["gate_id"] for e in events][:2] == ["jev", "jev"]
    assert pick_case1(events)["gate_id"] == "jev"


def test_case2_crossings_box_and_closest():
    gates = index(_rows("jev", ITEMS))
    events = case2_events(gates, "inject_preapproved", 0.5)
    assert len(events) == 1
    e = events[0]
    assert (e["variant_id"], e["toward_allow_repeats"], e["toward_deny_repeats"]) == ("d1/a", "1;3", "")
    assert pick_case2(events, "jev")["variant_id"] == "d1/a"
    assert pick_case2(events, "drex") is None
    closest = closest_case2(gates, "jev", "inject_preapproved")
    assert closest["variant_id"] == "d1/a"
    assert closest_case2(gates, "rules", "inject_preapproved") is None
