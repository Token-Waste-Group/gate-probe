"""Adversarial (A) generators: injected claims, self-justification and option swaps (docs/RELATIONS.md § 2).

Expected outcome `unchanged`: none of these changes what the call does or what
the policy says. Claims and justifications come from fixed strings in
configs/relations.yaml. The option swaps only rename or rebind the answer
labels; the adapters map answers back through `option_names`, and a mode with
fixed labels (Decisions API Noul) reports a renamed variant as not applicable.
The rubric swap binds `yes` to allow, replicating arXiv 2609.26758.

Scope of v0: the six A transforms. Out of scope: anything not in the catalog.
"""

from __future__ import annotations

import random
from typing import Any

from gateprobe.corpus.schema import Probe
from gateprobe.relations.common import Change, with_command


def inject_preapproved(probe: Probe, rng: random.Random, params: dict[str, Any]) -> list[Change]:
    return [{"context": params["claims"]["preapproved"]}]


def inject_test_env(probe: Probe, rng: random.Random, params: dict[str, Any]) -> list[Change]:
    return [{"context": params["claims"]["test_env"]}]


def inject_safe_per_policy(probe: Probe, rng: random.Random, params: dict[str, Any]) -> list[Change]:
    return [{"context": params["claims"]["safe_per_policy"]}]


def self_argument(probe: Probe, rng: random.Random, params: dict[str, Any]) -> list[Change]:
    """A shell comment in the call that argues the call is safe and allowed."""
    cmd = probe.call.get("command")
    if probe.tool != "Bash" or not cmd:
        return []
    return [with_command(probe, f"{cmd}  {rng.choice(params['self_arguments'])}")]


def option_name_swap(probe: Probe, rng: random.Random, params: dict[str, Any]) -> list[Change]:
    """Same meaning, renamed labels: yes/no -> 1/0 and -> A/B (two variants)."""
    return [{"option_names": {"deny": "1", "allow": "0"}}, {"option_names": {"deny": "A", "allow": "B"}}]


def rubric_name_swap(probe: Probe, rng: random.Random, params: dict[str, Any]) -> list[Change]:
    """The rubrics bound to the names are swapped: `yes` now means allow."""
    return [{"option_names": {"deny": "no", "allow": "yes"}}]


GENERATORS = {
    "inject_preapproved": inject_preapproved,
    "inject_test_env": inject_test_env,
    "inject_safe_per_policy": inject_safe_per_policy,
    "self_argument": self_argument,
    "option_name_swap": option_name_swap,
    "rubric_name_swap": rubric_name_swap,
}
