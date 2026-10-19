"""GateProbe: a metamorphic testing harness for coding-agent permission gates.

Subpackages, in data-flow order: `corpus` (probes, policies, schema), `relations`
(the E/M/I/A/P variant generators), `gates` (the adapter contract and the gate
adapters), `runner` (repeats, cache, replay, spend cap), `analysis` (floor, flip
rates, intervals, calibration), `report` (HTML), `hook` (the live Claude Code
hook). `config` loads `configs/*.yaml`; `cli` is the `gateprobe` command.

Scope of v0: the package skeleton (S1). Each subpackage names the plan step
that fills it in. Out of scope: everything those steps own.
"""

__version__ = "0.0.1"
