"""Build a gate adapter from its `configs/gates.yaml` entry.

Scope of v0: the adapters built so far (`decisions`); the others raise
`NotImplementedError` naming the step that builds them. Out of scope: the
adapters themselves.
"""

from __future__ import annotations

from gateprobe.config import GateConfig
from gateprobe.gates.base import GateAdapter

PENDING = {"judge": "R4 (Claude backend: R8)", "rules": "R3", "http": "a later step"}


def make_gate(cfg: GateConfig) -> GateAdapter:
    if cfg.adapter == "decisions":
        from gateprobe.gates.decisions import DecisionsGate

        return DecisionsGate.from_config(cfg)
    raise NotImplementedError(
        f"the {cfg.adapter!r} adapter isn't built yet (step {PENDING.get(cfg.adapter)})"
    )
