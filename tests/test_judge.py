"""Tests for the judge adapter against a fake OpenAI-compatible endpoint (no network).

Scope of v0: the frozen prompt and its fill, the request body, logprob-based
p_block (first non-blank token, labels renormalized, case-insensitive), the
verdict-only fallback, label swaps, the pin check and errors. Out of scope:
a live model (R5) and the Claude backend (R8).
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from gateprobe.config import load_gates
from gateprobe.gates.base import GateRequest, ToolCall
from gateprobe.gates.factory import make_gate
from gateprobe.gates.judge import JudgeError, JudgeGate

ROOT = Path(__file__).resolve().parents[1]
MODEL = "google/gemma-4-31B-it"
REQ = GateRequest(policy='{"rules": []}', call=ToolCall("Bash", {"command": "rm -rf ~/.ssh"}))


def completion(content: str, top: dict[str, float], lead: str | None = None, model: str = MODEL) -> dict:
    tokens = []
    if lead is not None:
        tokens.append({"token": lead, "logprob": 0.0, "top_logprobs": [{"token": lead, "logprob": 0.0}]})
    tokens.append(
        {
            "token": content,
            "logprob": math.log(max(top.values())),
            "top_logprobs": [{"token": t, "logprob": math.log(p)} for t, p in top.items()],
        }
    )
    return {
        "model": model,
        "choices": [{"message": {"role": "assistant", "content": content}, "logprobs": {"content": tokens}}],
        "usage": {"prompt_tokens": 600, "completion_tokens": 1},
    }


class Endpoint:
    def __init__(self, body: dict, status: int = 200) -> None:
        self.body, self.status, self.sent = body, status, []

    def __call__(self, url, headers, body):
        self.sent.append((url, headers, body))
        return self.status, self.body


def gate(endpoint, **kw) -> JudgeGate:
    return JudgeGate("judge-gemma", MODEL, "http://d.dgx:8000/v1", transport=endpoint, **kw)


def test_request_body_and_the_frozen_prompt():
    ep = Endpoint(completion("yes", {"yes": 0.9, "no": 0.1}))
    gate(ep).decide(REQ)
    url, headers, body = ep.sent[0]
    assert url == "http://d.dgx:8000/v1/chat/completions" and "Authorization" not in headers
    assert (body["temperature"], body["logprobs"], body["top_logprobs"]) == (0, True, 20)
    prompt = body["messages"][0]["content"]
    assert body["messages"][0]["role"] == "user" and len(body["messages"]) == 1
    assert '{"rules": []}' in prompt  # literal braces in a policy survive the fill
    assert '"command": "rm -rf ~/.ssh"' in prompt and "<context>\n(none)\n</context>" in prompt
    assert "- yes: Block the call" in prompt and "- no: Let the call run" in prompt
    assert prompt.index("- yes:") < prompt.index("- no:")
    assert "{" + "policy}" not in prompt and "(yes, no)" in prompt


def test_p_block_from_logprobs_renormalized_over_labels():
    d = gate(Endpoint(completion("yes", {"yes": 0.6, "Yes": 0.1, "no": 0.2, "maybe": 0.1}))).decide(REQ)
    assert d.verdict == "deny" and d.p_block == pytest.approx(0.7 / 0.9)
    assert d.raw["p_block_source"] == "logprobs"


def test_leading_blank_token_is_skipped():
    d = gate(Endpoint(completion("no", {"no": 0.8, "yes": 0.2}, lead=" "))).decide(REQ)
    assert (d.verdict, d.p_block) == ("allow", pytest.approx(0.2))


def test_rubric_swap_and_renamed_labels():
    swapped = GateRequest(REQ.policy, REQ.call, option_names={"deny": "no", "allow": "yes"})
    ep = Endpoint(completion("yes", {"yes": 0.75, "no": 0.25}))
    d = gate(ep).decide(swapped)
    assert "- no: Block the call" in ep.sent[0][2]["messages"][0]["content"]
    assert (d.verdict, d.p_block) == ("allow", pytest.approx(0.25))
    ab = GateRequest(REQ.policy, REQ.call, option_names={"deny": "A", "allow": "B"})
    d = gate(Endpoint(completion("A", {"A": 0.9, "B": 0.1}))).decide(ab)
    assert (d.verdict, d.p_block) == ("deny", pytest.approx(0.9))


def test_missing_logprobs_is_an_error_unless_verdict_only():
    body = completion("yes", {"yes": 1.0})
    del body["choices"][0]["logprobs"]
    with pytest.raises(JudgeError, match="no logprobs"):
        gate(Endpoint(body)).decide(REQ)
    d = gate(Endpoint(body), p_block_source="verdict_only").decide(REQ)
    assert (d.verdict, d.p_block, d.raw["p_block_source"]) == ("deny", 1.0, "verdict_only")


def test_answers_outside_the_labels_and_other_models_are_rejected():
    with pytest.raises(JudgeError, match="none of the labels"):
        gate(Endpoint(completion("probably", {"probably": 1.0}))).decide(REQ)
    with pytest.raises(JudgeError, match="not the pinned"):
        gate(Endpoint(completion("yes", {"yes": 1.0}, model="google/gemma-4-12b-it"))).decide(REQ)


def test_http_errors_and_missing_base_url():
    with pytest.raises(JudgeError) as e:
        gate(Endpoint({"error": {"message": "overloaded"}}, status=503)).decide(REQ)
    assert e.value.retryable and e.value.status == 503
    with pytest.raises(JudgeError, match="base_url"):
        JudgeGate("j", MODEL, None, transport=Endpoint({})).decide(REQ)


def test_key_is_sent_only_when_configured(monkeypatch):
    monkeypatch.setenv("JUDGE_KEY", "sk-test")
    ep = Endpoint(completion("no", {"no": 1.0}))
    gate(ep, api_key_env="JUDGE_KEY").decide(REQ)
    assert ep.sent[0][1]["Authorization"] == "Bearer sk-test"
    assert "sk-test" not in repr(gate(ep, api_key_env="JUDGE_KEY"))


def test_factory_and_config():
    gates = load_gates()
    judge = make_gate(gates["judge-gemma"])
    assert isinstance(judge, JudgeGate) and judge.model_id == MODEL and judge.p_block_source == "logprobs"
    assert judge.template == (ROOT / "configs" / "judge_prompt.md").read_text(encoding="utf-8")
    with pytest.raises(NotImplementedError, match="R8"):
        make_gate(gates["judge-claude"])


def test_cost_from_usage_and_request_bytes_are_stable():
    d = gate(
        Endpoint(completion("no", {"no": 1.0})), price_usd_per_mtok={"input": 1.0, "output": 2.0}
    ).decide(REQ)
    assert d.cost_usd == pytest.approx((600 * 1.0 + 1 * 2.0) / 1e6)
    g = gate(Endpoint({}))
    assert g.request_bytes(REQ) == g.request_bytes(REQ)
