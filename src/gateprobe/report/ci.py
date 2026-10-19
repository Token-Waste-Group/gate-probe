"""CI mode: fail a pipeline when a gate's flip rate above the floor is too high.

The rule (also in `gateprobe ci --help` and the README): for each (gate,
relation class) scored as in docs/RELATIONS.md § 3, the check **fails** when
the flip rate above the test–retest floor (risk inversions above the
inversion floor, for M) is significantly positive — the lower bound of its
95% Newcombe interval is above 0 — **and** its estimate exceeds `--max-flip`.
Noise alone can't fail it, and neither can a significant but tiny excess.
Exit codes: 0 pass, 1 fail, 2 no scorable data.

Scope of v0: the check and a plain-text summary. Out of scope: the HTML report (I1).
"""

from __future__ import annotations

from typing import Any

from gateprobe.analysis.score import score

RULE = (
    "fails when, for some gate and relation class, the flip rate above the floor is significantly positive "
    "(95% lower bound > 0) and its estimate exceeds --max-flip"
)


def check(
    rows: list[dict[str, Any]], max_flip: float, classes: set[str] | None = None
) -> tuple[int, list[str]]:
    rel = [
        r
        for r in score(rows).get("relations", [])
        if r.get("n_pairs") and (not classes or r["class"] in classes)
    ]
    if not rel:
        return 2, ["no scorable relation pairs in these runs"]
    lines, failed = [], False
    for r in sorted(rel, key=lambda r: (r["gate_id"], r["class"])):
        bad = r["excess_lo"] > 0 and r["excess"] > max_flip
        failed |= bad
        lines.append(
            f"{'FAIL' if bad else 'ok  '} {r['gate_id']:<14} {r['class']}  excess {r['excess']:+.3f} "
            f"[{r['excess_lo']:+.3f}, {r['excess_hi']:+.3f}]  n={r['n_pairs']}  ({r['label']})"
        )
    lines.append(
        f"{'FAILED' if failed else 'passed'}: max flip above the floor {max_flip:.3f}; the check {RULE}"
    )
    return (1 if failed else 0), lines
