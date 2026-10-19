"""Build a gate adapter from its `configs/gates.yaml` entry.

Scope of v0: the adapters built so far (`decisions`, `rules`, `judge` on an
OpenAI-compatible endpoint or the Anthropic API); the others raise
`NotImplementedError` naming the step that builds them. Out of scope: the
adapters themselves.
"""

from __future__ import annotations

from gateprobe.config import GateConfig
from gateprobe.gates.base import GateAdapter

PENDING = {"http": "a later step"}


def make_gate(cfg: GateConfig) -> GateAdapter:
    if cfg.adapter == "decisions":
        from gateprobe.gates.decisions import DecisionsGate

        return DecisionsGate.from_config(cfg)
    if cfg.adapter == "judge" and cfg.options.get("backend", "openai") == "openai":
        from gateprobe.gates.judge import JudgeGate

        return JudgeGate.from_config(cfg)
    if cfg.adapter == "judge" and cfg.options.get("backend") == "anthropic":
        from gateprobe.gates.claude import ClaudeJudgeGate

        return ClaudeJudgeGate.from_config(cfg)
    if cfg.adapter == "rules":
        from gateprobe.gates.rules import RulesGate

        return RulesGate(gate_id=cfg.name, model_id=cfg.model)
    raise NotImplementedError(
        f"the {cfg.adapter!r} adapter isn't built yet (step {PENDING.get(cfg.adapter)})"
    )
