"""Irrelevance (I) generators: added text that must not move the verdict (docs/RELATIONS.md § 2).

Every inserted string comes from a fixed list in configs/relations.yaml, chosen
by the variant's seed. The lists are neutral by design: no claim about safety,
approval, the environment or the policy (those are A, not I).

Scope of v0: the five I transforms. Out of scope: anything not in the catalog.
"""

from __future__ import annotations

import random
from typing import Any

from gateprobe.corpus.schema import Probe
from gateprobe.relations.common import Change, with_command


def timestamp(probe: Probe, rng: random.Random, params: dict[str, Any]) -> list[Change]:
    return [{"context": f"Current time: {rng.choice(params['timestamps'])}"}]


def benign_prior_output(probe: Probe, rng: random.Random, params: dict[str, Any]) -> list[Change]:
    return [{"context": "Previous tool output:\n" + rng.choice(params["prior_outputs"]).rstrip("\n")}]


def code_comment(probe: Probe, rng: random.Random, params: dict[str, Any]) -> list[Change]:
    cmd = probe.call.get("command")
    if probe.tool != "Bash" or not cmd:
        return []
    return [with_command(probe, f"{cmd}  {rng.choice(params['comments'])}")]


def chit_chat(probe: Probe, rng: random.Random, params: dict[str, Any]) -> list[Change]:
    return [{"context": rng.choice(params["chit_chat"])}]


def whitespace_padding(probe: Probe, rng: random.Random, params: dict[str, Any]) -> list[Change]:
    blank = "\n" * rng.randint(2, 4)
    return [{"context": blank + " " * rng.randint(2, 6) + "\n"}]


GENERATORS = {
    "timestamp": timestamp,
    "benign_prior_output": benign_prior_output,
    "code_comment": code_comment,
    "chit_chat": chit_chat,
    "whitespace_padding": whitespace_padding,
}
