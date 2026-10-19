"""Tests for the probe corpus: the committed files validate, are complete, and rebuild byte for byte.

Scope of v0: probes/corpus.jsonl, docs/CORPUS.md's generated counts, and the
template expansion. Out of scope: policies (C3) and variants (C4, C5).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gateprobe.corpus.build import (
    build,
    counts_markdown,
    expand_template,
    load_config,
    splice_counts,
    to_jsonl,
)
from gateprobe.corpus.schema import FAMILIES, RISK_TIERS, Probe, load_jsonl
from gateprobe.relations.normalize import normalize

ROOT = Path(__file__).resolve().parents[1]
CONFIG = load_config(ROOT / "configs" / "corpus.yaml")
CORPUS = ROOT / "probes" / "corpus.jsonl"


@pytest.fixture(scope="module")
def probes() -> list[Probe]:
    return load_jsonl(CORPUS, Probe)


def test_committed_corpus_is_complete(probes):
    assert len(probes) >= 300
    assert {p.risk_tier for p in probes} == set(RISK_TIERS)
    assert {p.family for p in probes} == set(FAMILIES)
    assert {p.policy_id for p in probes} == set(CONFIG["policies"])
    templates = {t["name"] for t in CONFIG["templates"]}
    assert all(p.source.startswith("template:") and p.source.split(":", 1)[1] in templates for p in probes)


def test_no_duplicate_call_under_the_same_policy(probes):
    keys = [json.dumps([p.tool, p.call, p.policy_id], sort_keys=True) for p in probes]
    assert len(keys) == len(set(keys))


def test_rebuild_reproduces_the_committed_files():
    rebuilt = build(CONFIG)
    assert to_jsonl(rebuilt) == CORPUS.read_text(encoding="utf-8")
    sheet = (ROOT / "docs" / "CORPUS.md").read_text(encoding="utf-8")
    assert splice_counts(sheet, counts_markdown(rebuilt)) == sheet


def test_no_real_hosts_in_network_calls(probes):
    for p in probes:
        text = json.dumps(p.call)
        for scheme in ("https://", "http://"):
            for chunk in text.split(scheme)[1:]:
                host = chunk.split("/")[0].split('"')[0]
                assert host.endswith(("example.com", "example.net")), (p.id, host)


def test_template_expansion_params_cases_and_literal_braces():
    t = {
        "name": "t",
        "family": "shell",
        "tool": "Bash",
        "risk_tier": "read",
        "command": "ls {a} {b}",
        "params": {"a": ["1", "2"], "b": ["x"]},
    }
    assert [c["call"]["command"] for c in expand_template(t)] == ["ls 1 x", "ls 2 x"]
    t2 = {
        "name": "t2",
        "family": "filesystem",
        "tool": "Write",
        "risk_tier": "reversible_write",
        "args": {"file_path": "{f}", "content": "{c}"},
        "cases": [{"f": "a.json", "c": '{"k": 1}'}],
    }
    assert expand_template(t2)[0]["call"] == {"file_path": "a.json", "content": '{"k": 1}'}
    t3 = {"name": "t3", "family": "shell", "tool": "Bash", "risk_tier": "read", "command": "echo {}"}
    assert expand_template(t3)[0]["call"] == {"command": "echo {}"}


def test_every_probe_is_a_distinct_call_even_after_normalization(probes):
    keys = [normalize(p.tool, p.call) for p in probes]
    assert len(keys) == len(set(keys))


def test_target_semantics_and_duplicate_templates():
    assert len(build({**CONFIG, "target_size": 10})) == len(build(CONFIG))  # never below the distinct calls
    with pytest.raises(ValueError, match="target_size"):
        build({**CONFIG, "target_size": 10_000})  # more than every (call, policy) pair
    dup = {
        "name": "dup",
        "family": "shell",
        "tool": "Bash",
        "risk_tier": "reversible_write",
        "command": "rm --recursive --force build/",
    }  # rm -rf ./build, spelled differently
    with pytest.raises(ValueError, match="after normalization"):
        build({**CONFIG, "templates": [*CONFIG["templates"], dup]})


@pytest.mark.parametrize(
    "a, b, same",
    [
        ("rm -rf ./build", "rm --recursive --force build/", True),
        ("rm -rf ./build", "rm -fr 'build'", True),
        ("rm -rf ./build", "rm  -rf   ./build", True),
        ("rm -rf ./build", "rm -rf ./dist", False),
        ("git push origin main", "git push --force origin main", False),
    ],
)
def test_normalize(a, b, same):
    assert (normalize("Bash", {"command": a}) == normalize("Bash", {"command": b})) is same
