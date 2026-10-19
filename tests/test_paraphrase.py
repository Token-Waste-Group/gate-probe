"""Tests for the P class: parsing and rejecting rewrites, generation with a fake model,
building, and the frozen set.

Scope of v0: gateprobe.relations.paraphrase and scripts/paraphrase.py. Never calls a model.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from gateprobe.corpus.schema import Probe, Variant, load_jsonl
from gateprobe.relations.expand import to_jsonl
from gateprobe.relations.paraphrase import build, generate, load_config, parse_command

ROOT = Path(__file__).resolve().parents[1]
CFG = load_config(ROOT / "configs" / "paraphrase.yaml")
PROBES = load_jsonl(ROOT / "probes" / "corpus.jsonl", Probe)
GENERATED = load_jsonl(ROOT / "variants" / "generated.jsonl", Variant)


@pytest.mark.parametrize(
    "text, status",
    [
        ('{"command": "find build -delete"}', "ok"),
        ('Sure!\n```json\n{"command": "find build -delete"}\n```', "ok"),
        ('{"command": "rm --recursive --force build/"}', "same_call"),
        ('{"command": "rm -rf build"}', "same_call"),
        ('{"command": "a\\nb"}', "not_one_line"),
        ("no json here", "no_json"),
        ('{"cmd": "x"}', "no_json"),
    ],
)
def test_parse_command(text, status):
    assert parse_command(text, "rm -rf build")[1] == status


def fake_model(prompt: str) -> tuple[str, str]:
    if "Command:" in prompt:
        cmd = prompt.split("Command: ", 1)[1].split("\n", 1)[0]
        return json.dumps({"command": cmd + " && true"}), CFG["model"]
    return "Reworded policy.", CFG["model"]


def test_generate_covers_bash_minus_skipped_tiers_and_every_policy():
    raw = generate(PROBES, ROOT / "policies", CFG, fake_model)
    expected = {p.id for p in PROBES if p.tool == "Bash" and p.risk_tier not in CFG["command_skip_tiers"]}
    assert {r["probe_id"] for r in raw["commands"]} == expected
    assert not any(
        p.risk_tier == "exfiltration" for p in PROBES if p.id in {r["probe_id"] for r in raw["commands"]}
    )
    assert {r["policy_id"] for r in raw["policies"]} == {p.policy_id for p in PROBES}
    assert raw["generator"]["model"] == CFG["model"] and raw["generator"]["served_model"] == [CFG["model"]]


def test_build_parents_classes_and_rejections():
    raw = generate(PROBES, ROOT / "policies", CFG, fake_model)
    raw["commands"][0] |= {"status": "same_call", "rewrite": None}
    variants = build(raw, GENERATED)
    by_id = {v.id: v for v in GENERATED}
    assert {v.relation_class for v in variants} == {"P"}
    cmd = [v for v in variants if v.transform == "command_paraphrase"]
    pol = [v for v in variants if v.transform == "policy_paraphrase"]
    assert len(cmd) == len(raw["commands"]) - 1 and len(pol) == len(PROBES)
    for v in cmd:
        base = by_id[v.parent_id]
        assert base.relation_class == "base" and v.policy_rendering == base.policy_rendering
    for v in pol:
        parent = by_id[v.parent_id]
        assert parent.transform == "policy_format" and parent.policy_rendering == "prose"
        assert v.call == parent.call and v.policy_text == "Reworded policy."
    assert to_jsonl(variants) == to_jsonl(build(raw, GENERATED))  # deterministic


def test_the_frozen_set_rebuilds_from_the_raw_outputs_and_matches_its_sha256():
    raw_path = ROOT / "variants" / "paraphrase_raw.json"
    if not raw_path.exists():
        pytest.skip("the P set is not generated yet")
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    text = to_jsonl(build(raw, GENERATED))
    assert text == (ROOT / "variants" / "paraphrase.jsonl").read_text(encoding="utf-8")
    digest = (ROOT / "variants" / "paraphrase.sha256").read_text().split()[0]
    assert hashlib.sha256(text.encode("utf-8")).hexdigest() == digest
    assert raw["generator"]["model"] == CFG["model"] and raw["generator"]["revision"] == CFG["revision"]
    assert not any(
        v["relation_class"] == "P" for v in map(json.loads, (ROOT / "variants" / "generated.jsonl").open())
    )
