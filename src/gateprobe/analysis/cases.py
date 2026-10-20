"""Case-study selection (X5) from frozen run rows, by the rules pre-registered in
docs/experiments/x5-case-studies.md.

Case 1: E or P pairs on `irreversible`-tier probes whose majority verdict goes deny -> allow; the box
is the E event with the largest drop in mean p_block (P only if no E event exists). Case 2: one A
transform (`inject_preapproved`) whose p_block crosses tau between parent and variant at some
repeat; the box is the largest-drop crossing toward allow on the named gate.

Scope of v0: selection and listing only; the replay check is `gateprobe replay`. Out of scope:
rendering the paper box (R7).
"""

from __future__ import annotations

from typing import Any

from gateprobe.analysis.score import Gate

GATE_ORDER = ("jev", "rules", "judge-claude", "gpt-6-luna-decisions", "pplx-decider", "drex")


def _reps(it: Any) -> str:
    return "/".join(f"{v} {p:.3f}" for _, (v, p) in sorted(it.reps.items()))


def _rank(gate_id: str) -> int:
    return GATE_ORDER.index(gate_id) if gate_id in GATE_ORDER else len(GATE_ORDER)


def case1_events(gates: dict[str, Gate], tiers: dict[str, str], exclude: set[str]) -> list[dict[str, Any]]:
    """Every E or P pair on a destructive probe whose majority verdict goes deny -> allow."""
    out = []
    for g in sorted(gates.values(), key=lambda g: _rank(g.gate_id)):
        for cls in ("E", "P"):
            for x, y in g.pairs(cls):
                if tiers.get(y.probe_id) != "irreversible" or y.id in exclude:
                    continue
                if x.majority() == "deny" and y.majority() == "allow":
                    out.append(
                        {
                            "gate_id": g.gate_id,
                            "probe_id": y.probe_id,
                            "class": cls,
                            "transform": y.transform,
                            "parent_id": x.id,
                            "variant_id": y.id,
                            "parent_p_mean": x.mean_p(),
                            "variant_p_mean": y.mean_p(),
                            "drop": x.mean_p() - y.mean_p(),
                            "parent_reps": _reps(x),
                            "variant_reps": _reps(y),
                        }
                    )
    return out


def case2_events(gates: dict[str, Gate], transform: str, tau: float) -> list[dict[str, Any]]:
    """Every pair of the transform whose p_block lies on opposite sides of tau at some shared repeat."""
    out = []
    for g in sorted(gates.values(), key=lambda g: _rank(g.gate_id)):
        for x, y in g.pairs("A", transform):
            shared = sorted(set(x.reps) & set(y.reps))
            to_allow = [k for k in shared if x.reps[k][1] >= tau > y.reps[k][1]]
            to_deny = [k for k in shared if x.reps[k][1] < tau <= y.reps[k][1]]
            if to_allow or to_deny:
                out.append(
                    {
                        "gate_id": g.gate_id,
                        "probe_id": y.probe_id,
                        "parent_id": x.id,
                        "variant_id": y.id,
                        "toward_allow_repeats": ";".join(map(str, to_allow)),
                        "toward_deny_repeats": ";".join(map(str, to_deny)),
                        "parent_p_mean": x.mean_p(),
                        "variant_p_mean": y.mean_p(),
                        "drop": x.mean_p() - y.mean_p(),
                        "parent_reps": _reps(x),
                        "variant_reps": _reps(y),
                    }
                )
    return out


def pick_case1(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    for cls in ("E", "P"):
        pool = [e for e in events if e["class"] == cls]
        if pool:
            return min(pool, key=lambda e: (-e["drop"], _rank(e["gate_id"]), e["variant_id"]))
    return None


def pick_case2(events: list[dict[str, Any]], gate_id: str) -> dict[str, Any] | None:
    pool = [e for e in events if e["gate_id"] == gate_id and e["toward_allow_repeats"]]
    return min(pool, key=lambda e: (-e["drop"], e["variant_id"])) if pool else None


def closest_case2(gates: dict[str, Gate], gate_id: str, transform: str) -> dict[str, Any] | None:
    """With no crossing toward allow: the pair whose mean p_block drops most under the transform."""
    g = gates.get(gate_id)
    pairs = g.pairs("A", transform) if g else []
    if not pairs:
        return None
    x, y = min(pairs, key=lambda xy: (-(xy[0].mean_p() - xy[1].mean_p()), xy[1].id))
    return {
        "gate_id": gate_id,
        "parent_id": x.id,
        "variant_id": y.id,
        "parent_p_mean": x.mean_p(),
        "variant_p_mean": y.mean_p(),
        "drop": x.mean_p() - y.mean_p(),
        "parent_reps": _reps(x),
        "variant_reps": _reps(y),
    }
