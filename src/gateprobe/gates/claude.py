"""The Claude judge (`judge` adapter, `backend: anthropic`): the frozen judge prompt on the Anthropic API.

Written from the claude-api skill's Python guides (README, batches, structured
outputs), not from memory. The prompt is `configs/judge_prompt.md`, filled
exactly as for the OpenAI-compatible judge (`JudgeGate.prompt`). The answer
comes back through structured output (`output_config.format`, a JSON schema
built per request): `label` (one of the item's option labels) and
`probabilities` (one number per label). p_block = P(deny label) / P(all labels),
a *stated* probability recorded as such (`p_block_source: stated`), never a
logprob. Opus 5.5 keeps thinking on and rejects sampling parameters, so the
config pins `effort`, not a temperature; thinking counts toward `max_tokens`.
A `refusal` stop reason raises `GateRefusal`: its own outcome, never re-run on
another model.

Scope of v0: request params (shared by the synchronous and the batch path),
response parsing from SDK objects or dicts, cost from usage at the configured
prices (half for batch results; a refusal carries its cost too), and a synchronous `decide` for single calls.
The SDK is the optional `[claude]` extra, imported lazily. Out of scope:
batch submission and polling (runner/batch.py).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from gateprobe.config import GateConfig, is_pinned
from gateprobe.gates.base import GateAdapter, GateDecision, GateRefusal, GateRequest
from gateprobe.gates.judge import PROMPT, JudgeError, JudgeGate, _norm


def _as_dict(message: Any) -> dict[str, Any]:
    if isinstance(message, dict):
        return message
    if hasattr(message, "to_dict"):
        return message.to_dict()
    return json.loads(message.model_dump_json())


class ClaudeJudgeGate(GateAdapter):
    mode = "judge"

    def __init__(
        self,
        gate_id: str,
        model: str,
        effort: str | None = None,
        max_tokens: int = 4096,
        prompt_path: Path = PROMPT,
        api_key_env: str = "ANTHROPIC_API_KEY",
        price_usd_per_mtok: dict[str, float] | None = None,
        client: Any = None,
    ) -> None:
        if not is_pinned(model):
            raise ValueError(f"model {model!r} is not a pinned version")
        self.gate_id, self.model_id, self.effort, self.max_tokens = gate_id, model, effort, max_tokens
        self.api_key_env = api_key_env
        self.price = price_usd_per_mtok or {}
        # The prompt fill is shared with the OpenAI-compatible judge, so both judges see identical text.
        self._prompter = JudgeGate(
            gate_id, model, base_url=None, prompt_path=prompt_path, transport=lambda *a: (500, {})
        )
        self._client = client

    @classmethod
    def from_config(cls, cfg: GateConfig, client: Any = None) -> ClaudeJudgeGate:
        o = cfg.options
        prompt = o.get("prompt")
        return cls(
            gate_id=cfg.name,
            model=cfg.model,
            effort=o.get("effort"),
            max_tokens=int(o.get("max_tokens", 4096)),
            prompt_path=PROMPT.parents[1] / prompt if prompt else PROMPT,
            api_key_env=o.get("api_key_env", "ANTHROPIC_API_KEY"),
            price_usd_per_mtok=o.get("price_usd_per_mtok"),
            client=client,
        )

    def __repr__(self) -> str:
        return f"ClaudeJudgeGate({self.gate_id!r}, {self.model_id!r}, effort={self.effort!r})"

    def client(self) -> Any:
        if self._client is None:
            import anthropic  # the optional [claude] extra

            if not os.environ.get(self.api_key_env):
                raise JudgeError(f"{self.api_key_env} is not set", status=401)
            self._client = anthropic.Anthropic(api_key=os.environ[self.api_key_env])
        return self._client

    # -- request ----------------------------------------------------------
    @staticmethod
    def schema(labels: list[str]) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "label": {"type": "string", "enum": labels, "description": "The option label you choose."},
                "probabilities": {
                    "type": "object",
                    "description": "For each option label, your probability (0 to 1) that it is the right "
                    "answer. They sum to 1.",
                    "properties": {label: {"type": "number"} for label in labels},
                    "required": labels,
                    "additionalProperties": False,
                },
            },
            "required": ["label", "probabilities"],
            "additionalProperties": False,
        }

    def params(self, request: GateRequest) -> dict[str, Any]:
        names = request.option_names
        labels = [names[v] for v in ("deny", "allow", "ask") if v in names]
        output_config: dict[str, Any] = {"format": {"type": "json_schema", "schema": self.schema(labels)}}
        if self.effort:
            output_config["effort"] = self.effort
        return {
            "model": self.model_id,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": self._prompter.prompt(request)}],
            "output_config": output_config,
        }

    def request_bytes(self, request: GateRequest) -> bytes:
        return json.dumps(self.params(request), ensure_ascii=False).encode("utf-8")

    # -- response ---------------------------------------------------------
    def parse(self, message: Any, names: dict[str, str], latency_ms: float, batch: bool) -> GateDecision:
        msg = _as_dict(message)
        usage = msg.get("usage") or {}
        if msg.get("stop_reason") == "refusal":  # still billed: usage and cost go with the refusal
            raise GateRefusal(
                "the model declined",
                {
                    "stop_details": msg.get("stop_details"),
                    "id": msg.get("id"),
                    "usage": usage,
                    "cost_usd": self.cost(usage, batch),
                },
            )
        served = msg.get("model")
        if served and served != self.model_id:
            raise JudgeError(f"served model {served!r} is not the pinned {self.model_id!r}", status=200)
        text = next((b.get("text", "") for b in msg.get("content", []) if b.get("type") == "text"), "")
        try:
            answer = json.loads(text)
        except json.JSONDecodeError as e:
            raise JudgeError(f"no JSON answer (stop_reason {msg.get('stop_reason')!r})", status=200) from e
        label_to_verdict = {_norm(label): v for v, label in names.items()}
        chosen = _norm(str(answer.get("label", "")))
        if chosen not in label_to_verdict:
            raise JudgeError(f"label {answer.get('label')!r} is none of {sorted(names.values())}", status=200)
        probs = {_norm(k): max(0.0, float(v)) for k, v in (answer.get("probabilities") or {}).items()}
        total = sum(probs.get(_norm(label), 0.0) for label in names.values())
        if total <= 0:
            raise JudgeError("stated probabilities are all zero", status=200)
        p_block = probs.get(_norm(names["deny"]), 0.0) / total
        return GateDecision(
            verdict=label_to_verdict[chosen],
            p_block=min(max(p_block, 0.0), 1.0),
            raw={**msg, "p_block_source": "stated", "batch": batch},
            gate_id=self.gate_id,
            model_id=self.model_id,
            latency_ms=latency_ms,
            cost_usd=self.cost(usage, batch),
        )

    def cost(self, usage: dict[str, Any], batch: bool) -> float:
        factor = 0.5 if batch else 1.0  # the Batch API halves token prices
        tokens_in, tokens_out = usage.get("input_tokens", 0) or 0, usage.get("output_tokens", 0) or 0
        return (
            factor
            * (tokens_in * self.price.get("input", 0.0) + tokens_out * self.price.get("output", 0.0))
            / 1e6
        )

    # -- synchronous call -------------------------------------------------
    def decide(self, request: GateRequest) -> GateDecision:
        start = time.perf_counter()
        message = self.client().messages.create(**self.params(request))
        return self.parse(message, request.option_names, (time.perf_counter() - start) * 1000.0, batch=False)
