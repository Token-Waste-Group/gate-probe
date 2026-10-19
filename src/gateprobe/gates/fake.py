"""A deterministic fake gate for tests: no network, no randomness, no cost.

Scope of v0: `p_block` is a stable hash of the whole request, so any change to
the policy, the call or the context can move it; `overrides` pins `p_block` for
calls whose command contains a given substring, so tests can stage a
dangerous call or a flip on purpose. Out of scope: simulating test-retest
noise (a test that needs noise builds it on top of this).
"""

from __future__ import annotations

import hashlib
import json

from gateprobe.gates.base import GateAdapter, GateDecision, GateRequest


class FakeGate(GateAdapter):
    def __init__(
        self,
        gate_id: str = "fake",
        model_id: str = "fake-1",
        threshold: float = 0.5,
        overrides: dict[str, float] | None = None,
    ) -> None:
        self.gate_id = gate_id
        self.model_id = model_id
        self.threshold = threshold
        self.overrides = dict(overrides or {})

    def p_block(self, request: GateRequest) -> float:
        command = str(request.call.args.get("command", ""))
        for needle, p in self.overrides.items():
            if needle in command:
                return p
        payload = json.dumps(
            [request.policy, request.call.tool, request.call.args, request.context, request.option_names],
            sort_keys=True,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).digest()
        return int.from_bytes(digest[:8], "big") / 2**64

    def decide(self, request: GateRequest) -> GateDecision:
        p = self.p_block(request)
        return GateDecision(
            verdict="deny" if p >= self.threshold else "allow",
            p_block=p,
            raw={"fake": True, "p_block": p},
            gate_id=self.gate_id,
            model_id=self.model_id,
            latency_ms=0.0,
            cost_usd=0.0,
        )
