"""Tests for the policy renderings: one source, four equivalent renderings, all committed and current.

Scope of v0: configs/policies.yaml, gateprobe.corpus.render and the files under
policies/. Out of scope: the rule gate's pattern sets (R3).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gateprobe.corpus.render import (
    FILES,
    SEMANTICS,
    PolicyError,
    _phrase,
    load_source,
    parse_rules,
    render,
    render_all,
)
from gateprobe.corpus.schema import RENDERINGS, Probe, load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SRC = load_source(ROOT / "configs" / "policies.yaml")


def test_committed_renderings_match_a_fresh_render():
    for rel, text in render_all(SRC).items():
        assert (ROOT / "policies" / rel).read_text(encoding="utf-8") == text, rel


@pytest.mark.parametrize("policy", SRC["policies"], ids=lambda p: p["id"])
def test_yaml_and_json_parse_back_to_the_source_rules(policy):
    want = [{k: r[k] for k in ("effect", "action", "scope")} for r in policy["rules"]]
    for fmt in ("yaml", "json"):
        assert parse_rules(render(SRC, policy, fmt), fmt) == want


@pytest.mark.parametrize("policy", SRC["policies"], ids=lambda p: p["id"])
def test_prose_and_bullets_state_every_rule_and_the_semantics(policy):
    for fmt in ("prose", "bullets"):
        text = render(SRC, policy, fmt)
        assert SEMANTICS in text
        for rule in policy["rules"]:
            assert _phrase(SRC, rule) in text, (fmt, rule)
    bullets = render(SRC, policy, "bullets")
    allowed, denied = bullets.split("Not allowed:")
    for rule in policy["rules"]:
        assert (_phrase(SRC, rule) in allowed) == (rule["effect"] == "allow")


def test_every_corpus_policy_exists_in_every_rendering():
    ids = {p["id"] for p in SRC["policies"]}
    corpus_ids = {p.policy_id for p in load_jsonl(ROOT / "probes" / "corpus.jsonl", Probe)}
    assert corpus_ids <= ids
    for pid in ids:
        for fmt in RENDERINGS:
            assert (ROOT / "policies" / pid / FILES[fmt]).exists()


def test_unknown_action_or_effect_is_rejected(tmp_path):
    bad = tmp_path / "p.yaml"
    bad.write_text(
        "actions: {read: read files}\nscopes: {anywhere: anywhere}\n"
        "policies:\n  - {id: x, title: X, description: d,\n"
        "     rules: [{effect: allow, action: fly, scope: anywhere}]}\n",
        encoding="utf-8",
    )
    with pytest.raises(PolicyError):
        load_source(bad)
