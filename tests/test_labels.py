"""Tests for the hand-labeled subset: the stratified sample, label records, the majority vote, and the CLI.

Scope of v0: gateprobe.corpus.labels, scripts/label_cli.py, and the labels
reaching analyze/report. Out of scope: the labels themselves (H2).
"""

from __future__ import annotations

import importlib.util
import io
import json
import shutil
from collections import Counter
from pathlib import Path

import pytest

from gateprobe import cli
from gateprobe.corpus.labels import append_label, majority, read_labels, sample
from gateprobe.corpus.schema import Probe, load_jsonl

ROOT = Path(__file__).resolve().parents[1]
PROBES = load_jsonl(ROOT / "probes" / "corpus.jsonl", Probe)


def _cli():
    spec = importlib.util.spec_from_file_location("label_cli", ROOT / "scripts" / "label_cli.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_sample_is_stratified_seeded_and_matches_the_committed_file():
    picked = sample(PROBES, 60, 13)
    assert len(picked) == 60 and len({p.id for p in picked}) == 60
    tiers = Counter(p.risk_tier for p in picked)
    available = Counter(p.risk_tier for p in PROBES)
    assert all(tiers[t] == min(available[t], max(tiers.values())) or tiers[t] >= 15 for t in available)
    assert tiers["exfiltration"] == available["exfiltration"]  # a small tier is taken whole
    assert [p.id for p in picked] == [p.id for p in sample(PROBES, 60, 13)]
    committed = [
        json.loads(line)["probe_id"]
        for line in (ROOT / "probes" / "label_sample.jsonl").read_text().splitlines()
    ]
    assert committed == [p.id for p in picked]


def test_records_and_majority(tmp_path):
    f = tmp_path / "labels.jsonl"
    append_label(f, "p1", "deny", "a")
    append_label(f, "p1", "deny", "b")
    append_label(f, "p1", "allow", "c")
    append_label(f, "p2", "deny", "a")
    append_label(f, "p2", "allow", "b")  # tie -> unlabeled
    append_label(f, "p3", "allow", "a")
    append_label(f, "p3", "deny", "a")  # a's latest answer counts
    assert majority(read_labels(f)) == {"p1": "deny", "p3": "deny"}
    with pytest.raises(ValueError):
        append_label(f, "p4", "block", "a")
    with pytest.raises(ValueError):
        append_label(f, "p4", "deny", " ")


def test_label_cli_records_skips_and_resumes(tmp_path):
    for d in ("probes", "policies"):
        shutil.copytree(ROOT / d, tmp_path / d)
    (tmp_path / "probes" / "labels.jsonl").unlink(missing_ok=True)
    answers = iter(["x", "d", "s", "a", "q"])
    mod = _cli()
    assert mod.run("me", root=tmp_path, ask=lambda _: next(answers), out=io.StringIO()) == 0
    recs = read_labels(tmp_path / "probes" / "labels.jsonl")
    assert [r["label"] for r in recs] == ["deny", "allow"] and {r["labeler"] for r in recs} == {"me"}
    out = io.StringIO()
    mod.run("me", root=tmp_path, ask=lambda _: "q", out=out)
    assert out.getvalue().startswith("2 labeled, 58 to go")


def test_analyze_uses_the_majority_labels(tmp_path):
    probes = tmp_path / "probes.jsonl"
    rec = {
        "tool": "Bash",
        "call": {"command": "ls"},
        "risk_tier": "read",
        "policy_id": "x",
        "source": "template:t",
        "family": "shell",
    }
    probes.write_text(json.dumps({**rec, "id": "p1"}) + "\n", encoding="utf-8")
    append_label(tmp_path / "labels.jsonl", "p1", "deny", "a")
    assert cli._labels(probes) == {"p1": "deny"}
