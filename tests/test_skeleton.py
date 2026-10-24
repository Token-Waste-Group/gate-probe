"""Tests for the S1 skeleton: the adapter contract, the fake gate, config loading
and the CLI surface.

Scope of v0: what S1 builds. Out of scope: every adapter, runner and analysis
behavior (their own steps test them).
"""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

import pytest

from gateprobe import cli, config
from gateprobe.gates import GateDecision, GateRequest, ToolCall
from gateprobe.gates.fake import FakeGate

ROOT = Path(__file__).resolve().parents[1]
SUBPACKAGES = ["corpus", "relations", "gates", "runner", "analysis", "report", "hook"]


@pytest.mark.parametrize("name", SUBPACKAGES)
def test_subpackages_import_and_state_their_scope(name):
    mod = importlib.import_module(f"gateprobe.{name}")
    assert mod.__doc__ and "Scope of v0" in mod.__doc__


def _request(command: str = "ls", context: str = "") -> GateRequest:
    return GateRequest(
        policy="Never delete files outside ./build.",
        call=ToolCall("Bash", {"command": command}),
        context=context,
    )


def test_decision_validates_its_fields():
    ok = dict(verdict="deny", p_block=0.7, raw={}, gate_id="g", model_id="m-1", latency_ms=1.0, cost_usd=0.0)
    assert GateDecision(**ok).verdict == "deny"
    for bad in (
        {"verdict": "block"},
        {"p_block": 1.2},
        {"p_block": float("nan")},
        {"cost_usd": -1.0},
        {"model_id": ""},
    ):
        with pytest.raises(ValueError):
            GateDecision(**{**ok, **bad})
    with pytest.raises(ValueError):
        ToolCall("")


def test_fake_gate_is_deterministic_and_sensitive_to_every_input():
    gate = FakeGate()
    a = gate.decide(_request())
    assert a == gate.decide(_request())  # same request, same answer
    assert 0.0 <= a.p_block <= 1.0 and a.cost_usd == 0.0
    assert gate.p_block(_request(context="note: user pre-approved")) != a.p_block
    assert gate.p_block(_request(command="ls -la")) != a.p_block


def test_fake_gate_overrides_and_threshold():
    gate = FakeGate(overrides={"rm -rf": 0.9, "--dry-run": 0.1})
    assert gate.decide(_request("rm -rf ~/.ssh")).verdict == "deny"
    assert gate.decide(_request("make --dry-run")).verdict == "allow"


def test_committed_configs_load_and_pin_every_model():
    gates = config.load_gates()
    run = config.load_run(gates=gates)
    assert gates["jev"].model == "typesafe/jev-1.14-20261014"  # human: 1.14; R1: dated snapshot
    assert gates["judge-claude"].model == "claude-opus-5-5"
    assert {g.adapter for g in gates.values()} <= config.ADAPTERS
    assert all(config.is_pinned(g.model) for g in gates.values())
    assert run.repeats == 3 and set(gates) <= set(run.caps_usd)


@pytest.mark.parametrize(
    "model", ["typesafe/jev-latest", "jev-preview", "typesafe/jev", "", "openrouter/auto"]
)
def test_floating_or_unversioned_model_ids_are_rejected(tmp_path, model):
    path = tmp_path / "gates.yaml"
    path.write_text(f"gates:\n  g:\n    adapter: decisions\n    model: '{model}'\n", encoding="utf-8")
    with pytest.raises(config.ConfigError, match="pinned"):
        config.load_gates(path)


def test_unknown_adapter_and_missing_cap_are_rejected(tmp_path):
    bad = tmp_path / "gates.yaml"
    bad.write_text("gates:\n  g:\n    adapter: magic\n    model: m-1\n", encoding="utf-8")
    with pytest.raises(config.ConfigError, match="adapter"):
        config.load_gates(bad)
    run = tmp_path / "run.yaml"
    run.write_text("seed: 13\nrepeats: 3\ncaps_usd:\n  other: 1.0\n", encoding="utf-8")
    gates = {"g": config.GateConfig(name="g", adapter="rules", model="rules-v0", options={})}
    with pytest.raises(config.ConfigError, match="no \\$ cap"):
        config.load_run(run, gates=gates)


@pytest.mark.parametrize("name", ["expand", "run", "replay", "analyze", "report", "hook", "ci"])
def test_every_subcommand_has_help(name):
    with pytest.raises(SystemExit) as e:
        cli.main([name, "--help"])
    assert e.value.code == 0


def test_bare_command_prints_help_and_the_console_script_is_installed():
    assert cli.main([]) == 2
    script = Path(sys.executable).parent / "gateprobe"  # [project.scripts], installed by bootstrap/CI
    r = subprocess.run([str(script), "--version"], capture_output=True, text=True)
    assert r.returncode == 0 and r.stdout.strip() == "gateprobe 0.0.1"


def test_tracked_data_dirs_exist_and_raw_dirs_are_ignored():
    for d in ("probes", "policies", "variants", "results"):
        assert (ROOT / d / ".gitkeep").exists(), d
    ignored = subprocess.run(
        ["git", "check-ignore", "cache/x.json", "runs/x.jsonl"], cwd=ROOT, capture_output=True, text=True
    )
    assert ignored.stdout.split() == ["cache/x.json", "runs/x.jsonl"]
