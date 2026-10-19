"""Tests for the CI mode: pass/fail/no-data exit codes on fixture runs, the class filter, and the action file.

Scope of v0: `gateprobe ci` and action.yml. Out of scope: running the action on GitHub.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from gateprobe import cli
from gateprobe.report.ci import RULE, check

ROOT = Path(__file__).resolve().parents[1]


def runs(flips: int, n: int = 40) -> list[dict]:
    """n probes, each with a base item and one E variant (2 repeats, identical within an item);
    `flips` of the E variants change the verdict. The floor is 0."""
    rows = []
    for i in range(n):
        base = {
            "gate_id": "g",
            "mode": "noul",
            "probe_id": f"p{i}",
            "status": "ok",
            "cached": False,
            "cost_usd": 0.0,
            "latency_ms": 1.0,
        }
        for k in (1, 2):
            rows.append(
                {
                    **base,
                    "variant_id": f"p{i}/base",
                    "parent_id": None,
                    "relation_class": "base",
                    "transform": "identity",
                    "repeat": k,
                    "verdict": "deny",
                    "p_block": 0.9,
                }
            )
            v = "allow" if i < flips else "deny"
            rows.append(
                {
                    **base,
                    "variant_id": f"p{i}/e",
                    "parent_id": f"p{i}/base",
                    "relation_class": "E",
                    "transform": "flag_order",
                    "repeat": k,
                    "verdict": v,
                    "p_block": 0.1 if v == "allow" else 0.9,
                }
            )
    return rows


def test_pass_fail_and_no_data():
    assert check(runs(0), 0.05)[0] == 0
    code, lines = check(runs(12), 0.05)  # 12/40 = 0.30 above a zero floor, clearly significant
    assert code == 1 and lines[0].startswith("FAIL") and "FAILED" in lines[-1]
    assert check(runs(12), 0.5)[0] == 0  # significant, but below the tolerated excess
    assert check(runs(1), 0.0)[0] == 0  # 1/40: not significant, so noise can't fail CI
    assert check([], 0.05)[0] == 2


def test_class_filter():
    assert check(runs(12), 0.05, classes={"M"})[0] == 2
    assert check(runs(12), 0.05, classes={"E"})[0] == 1


def test_cli_and_rule_in_help(tmp_path, capsys):
    f = tmp_path / "run.jsonl"
    f.write_text("".join(json.dumps(r) + "\n" for r in runs(12)), encoding="utf-8")
    assert cli.main(["ci", "--runs", str(f), "--max-flip", "0.05"]) == 1
    assert "FAIL" in capsys.readouterr().out
    assert "lower bound" in RULE and "--max-flip" in RULE


def test_action_runs_the_cli():
    action = yaml.safe_load((ROOT / "action.yml").read_text(encoding="utf-8"))
    assert action["runs"]["using"] == "composite" and set(action["inputs"]) == {"runs", "max-flip", "classes"}
    assert any("gateprobe ci" in s.get("run", "") for s in action["runs"]["steps"])
