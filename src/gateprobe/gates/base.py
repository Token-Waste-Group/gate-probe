"""The adapter contract every gate implements: (policy, tool call, context) in;
verdict, block probability, raw response, gate id, pinned model id, latency
and cost out.

Scope of v0: the request/decision records with their validation, and the
abstract adapter. Out of scope: transport, retries and caching (the runner, R2),
and any vendor specifics (one adapter module per gate).
"""

from __future__ import annotations

import json
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal

from gateprobe.corpus.schema import DEFAULT_OPTION_NAMES

Verdict = Literal["allow", "ask", "deny"]
VERDICTS: frozenset[str] = frozenset({"allow", "ask", "deny"})


@dataclass(frozen=True)
class ToolCall:
    """One coding-agent tool call, e.g. `ToolCall("Bash", {"command": "rm -rf build"})`."""

    tool: str
    args: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.tool:
            raise ValueError("ToolCall.tool must be a non-empty tool name")


@dataclass(frozen=True)
class GateRequest:
    """What a gate sees: one rendering of the policy, the call, the surrounding context, and
    the option names it answers with (semantic verdict -> label; the A-class swaps change them)."""

    policy: str
    call: ToolCall
    context: str = ""
    option_names: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_OPTION_NAMES))
    policy_id: str = ""  # which policy the text renders; only the rule gate reads it


@dataclass(frozen=True)
class GateDecision:
    """A gate's answer. `p_block` is the probability that the gate blocks the call."""

    verdict: Verdict
    p_block: float
    raw: dict[str, Any]
    gate_id: str
    model_id: str
    latency_ms: float
    cost_usd: float

    def __post_init__(self) -> None:
        if self.verdict not in VERDICTS:
            raise ValueError(f"verdict must be one of {sorted(VERDICTS)}, got {self.verdict!r}")
        if not (math.isfinite(self.p_block) and 0.0 <= self.p_block <= 1.0):
            raise ValueError(f"p_block must be in [0, 1], got {self.p_block!r}")
        if self.latency_ms < 0 or self.cost_usd < 0:
            raise ValueError("latency_ms and cost_usd must be non-negative")
        if not self.gate_id or not self.model_id:
            raise ValueError("gate_id and model_id must be set")


class GateAdapter(ABC):
    """One gate under test. Subclasses set `gate_id` and a pinned `model_id`."""

    gate_id: str
    model_id: str

    @abstractmethod
    def decide(self, request: GateRequest) -> GateDecision:
        """Ask the gate once. Repeats, retries and caching are the runner's job."""

    def request_bytes(self, request: GateRequest) -> bytes:
        """The exact request this gate would send, as canonical bytes: the core of the cache key.
        Adapters with a wire format override it with their request body. It never holds a secret.
        Never sort keys: argument order is an input (the json_key_order transform changes only it)."""
        fields = [request.policy, request.call.tool, request.call.args, request.context, request.option_names]
        return json.dumps(fields, ensure_ascii=False).encode("utf-8")
