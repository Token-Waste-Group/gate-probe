"""Gate adapters. Every gate sits behind one contract (`base.GateAdapter`), so a
new vendor is one file.

Scope of v0: the contract (`base`) and a deterministic fake gate for tests
(`fake`). Out of scope (later steps): the Decisions API adapter (R1), the rule
gate (R3), the judge adapter (R4) and its Claude backend (R8), the `http` gate.
"""

from gateprobe.gates.base import GateAdapter, GateDecision, GateRequest, ToolCall

__all__ = ["GateAdapter", "GateDecision", "GateRequest", "ToolCall"]
