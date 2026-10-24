"""Tests for the Decisions API adapter, on recorded responses and a fake transport (no network).

Scope of v0: request bodies per mode and option names, response parsing,
the pin check, errors, cost and key handling. The fixtures in tests/fixtures/
are real Jev 1.14 responses recorded by scripts/decisions_smoke.py.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gateprobe.config import load_gates
from gateprobe.gates.base import GateRequest, ToolCall
from gateprobe.gates.decisions import DecisionsError, DecisionsGate, NotApplicable

FIXTURES = Path(__file__).resolve().parent / "fixtures"
PINNED = "typesafe/jev-1.14-20261014"
REQ = GateRequest(policy="policy: workspace-dev", call=ToolCall("Bash", {"command": "rm -rf ~/.ssh"}))


def _fixture(mode: str) -> dict:
    return json.loads((FIXTURES / f"decisions_{mode}.json").read_text(encoding="utf-8"))


class Recorder:
    """A fake transport that records what it was sent and replays a canned response."""

    def __init__(self, status: int = 200, body: dict | None = None) -> None:
        self.status, self.body, self.sent = status, body or {}, []

    def __call__(self, url, headers, body):
        self.sent.append((url, headers, body))
        return self.status, self.body


@pytest.fixture(autouse=True)
def fake_key(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-not-a-real-key")


def test_config_builds_the_pinned_noul_gate():
    gate = DecisionsGate.from_config(load_gates()["jev"])
    assert (gate.model_id, gate.mode) == (PINNED, "noul")


@pytest.mark.parametrize("model", ["typesafe/jev-latest", "typesafe/jev"])
def test_unpinned_model_is_refused(model):
    with pytest.raises(ValueError, match="pinned"):
        DecisionsGate("jev", model)


def test_noul_request_and_recorded_response():
    t = Recorder(body=_fixture("noul"))
    d = DecisionsGate("jev", PINNED, transport=t).decide(REQ)
    url, headers, body = t.sent[0]
    assert url == "https://openrouter.ai/api/alpha/decisions"
    assert headers["Authorization"] == "Bearer sk-or-test-not-a-real-key"
    assert body["model"] == PINNED
    assert body["state"] == {
        "policy": "policy: workspace-dev",
        "tool": "Bash",
        "tool_input": {"command": "rm -rf ~/.ssh"},
        "context": "",
    }
    q = body["questions"]["gate"]
    assert q["type"] == "noul" and "should be blocked" in q["instructions"]
    assert set(q["criteria"]) == {"true", "false"} and q["criteria"]["true"].startswith("Block")
    assert (d.verdict, d.p_block) == ("deny", 0.95)
    assert d.cost_usd == pytest.approx(3.675e-05) and d.raw["id"].startswith("gen-dec-")


def test_noul_rubric_swap_asks_allowed_and_maps_back():
    swapped = GateRequest(REQ.policy, REQ.call, option_names={"deny": "no", "allow": "yes"})
    body = {**_fixture("noul"), "answers": {"gate": {"type": "noul", "noul": 0.2}}}
    t = Recorder(body=body)
    d = DecisionsGate("jev", PINNED, transport=t).decide(swapped)
    q = t.sent[0][2]["questions"]["gate"]
    assert "should be allowed" in q["instructions"] and q["criteria"]["true"].startswith("Let")
    assert d.p_block == pytest.approx(0.8) and d.verdict == "deny"


@pytest.mark.parametrize(
    "names",
    [
        {"deny": "1", "allow": "0"},
        {"deny": "A", "allow": "B"},
        {"deny": "deny", "allow": "allow", "ask": "ask"},
    ],
)
def test_noul_cannot_express_renamed_options(names):
    gate = DecisionsGate("jev", PINNED, transport=Recorder(body=_fixture("noul")))
    with pytest.raises(NotApplicable):
        gate.decide(GateRequest(REQ.policy, REQ.call, option_names=names))


def test_choice_request_and_recorded_response():
    t = Recorder(body=_fixture("choice"))
    d = DecisionsGate("jev", PINNED, mode="choice", transport=t).decide(REQ)
    q = t.sent[0][2]["questions"]["gate"]
    assert q["type"] == "choice" and set(q["criteria"]) == {"yes", "no"}
    assert q["criteria"]["yes"].startswith("Block")
    assert (d.verdict, d.p_block) == ("deny", 0.98)


def test_choice_with_renamed_and_swapped_labels():
    names = {"deny": "B", "allow": "A"}
    body = {
        **_fixture("choice"),
        "answers": {"gate": {"type": "choice", "choice": "A", "probabilities": {"A": 0.7, "B": 0.3}}},
    }
    t = Recorder(body=body)
    d = DecisionsGate("jev", PINNED, mode="choice", transport=t).decide(
        GateRequest(REQ.policy, REQ.call, option_names=names)
    )
    assert set(t.sent[0][2]["questions"]["gate"]["criteria"]) == {"A", "B"}
    assert (d.verdict, d.p_block) == ("allow", pytest.approx(0.3))


def test_a_different_served_model_is_rejected():
    body = {**_fixture("noul"), "model": "typesafe/jev-1.15-20261101"}
    with pytest.raises(DecisionsError, match="not the pinned"):
        DecisionsGate("jev", PINNED, transport=Recorder(body=body)).decide(REQ)


@pytest.mark.parametrize("status, retryable", [(429, True), (503, True), (400, False), (402, False)])
def test_http_errors_carry_status_and_retryability(status, retryable):
    t = Recorder(status=status, body={"error": {"code": status, "message": "nope"}})
    with pytest.raises(DecisionsError) as e:
        DecisionsGate("jev", PINNED, transport=t).decide(REQ)
    assert (e.value.status, e.value.retryable) == (status, retryable)
    assert "sk-or-test" not in str(e.value)


@pytest.mark.parametrize(
    "answer", [{"type": "noul", "noul": 1.3}, {"type": "noul"}, {"type": "noul", "noul": "x"}]
)
def test_malformed_noul_answers_are_rejected(answer):
    body = {**_fixture("noul"), "answers": {"gate": answer}}
    with pytest.raises(DecisionsError, match="probability"):
        DecisionsGate("jev", PINNED, transport=Recorder(body=body)).decide(REQ)


def test_missing_key_fails_before_any_request(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY")
    t = Recorder(body=_fixture("noul"))
    with pytest.raises(DecisionsError, match="not set"):
        DecisionsGate("jev", PINNED, transport=t).decide(REQ)
    assert t.sent == []


def test_cost_falls_back_to_configured_prices_and_repr_hides_the_key():
    body = {**_fixture("noul"), "usage": {"input_tokens": 1_000_000, "output_tokens": 10}}
    gate = DecisionsGate(
        "jev", PINNED, price_usd_per_mtok={"input": 0.042, "output": 0.0}, transport=Recorder(body=body)
    )
    assert gate.decide(REQ).cost_usd == pytest.approx(0.042)
    assert "sk-or" not in repr(gate)
