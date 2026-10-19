"""Shared machinery for the relation generators: shell tokens with their original
spelling, seeds, and variant records.

A generator is a function `(probe, rng, params) -> list[Change]`. Each change
is one variant: the fields it overrides on the parent (call, tool, context,
policy_rendering, policy_text, option_names). An empty list means the
transform doesn't apply to this probe, and the skip is counted. `make_variant`
turns a change into a schema-checked `Variant` carrying its parent, class,
transform, expected outcome and seed.

Scope of v0: a quote-aware whitespace tokenizer that keeps every token's
original text and the separators between tokens (so a transform changes only
what it means to change), the shell-operator check, per-(probe, transform)
seeds, and the variant builder. Out of scope: a full shell parser.
"""

from __future__ import annotations

import hashlib
import random
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from gateprobe.corpus.schema import CANONICAL_RENDERING, DEFAULT_OPTION_NAMES, EXPECTED, Probe, Variant

OPERATORS = ("|", "&&", "||", ";", ">", "<", "$(", "`", "&")
Change = dict[str, Any]
Generator = Callable[[Probe, random.Random, dict[str, Any]], list[Change]]


@dataclass
class Tokens:
    """A command split on whitespace outside quotes; `seps[i]` is the whitespace before `raw[i]`."""

    raw: list[str]
    seps: list[str]
    trailing: str = ""
    quoted: list[bool] = field(default_factory=list)

    @classmethod
    def split(cls, command: str) -> Tokens:
        raw, seps, quoted, buf, sep, quote, was_quoted = [], [], [], [], [], None, False
        for ch in command:
            if quote:
                buf.append(ch)
                quote = None if ch == quote else quote
            elif ch.isspace():
                if buf:
                    raw.append("".join(buf))
                    quoted.append(was_quoted)
                    buf, was_quoted = [], False
                sep.append(ch)
            else:
                if not buf:  # a token starts here (with a quote or not): record the whitespace before it
                    seps.append("".join(sep))
                    sep = []
                if ch in "'\"":
                    quote, was_quoted = ch, True
                buf.append(ch)
        if buf:
            raw.append("".join(buf))
            quoted.append(was_quoted)
        return cls(raw=raw, seps=seps, trailing="".join(sep), quoted=quoted)

    def join(self) -> str:
        return "".join(s + t for s, t in zip(self.seps, self.raw, strict=True)) + self.trailing


def is_simple(command: str) -> bool:
    """No pipes, chains, redirects or substitutions outside quotes."""
    out, quote = [], None
    for ch in command:
        if quote:
            quote = None if ch == quote else quote
            continue
        if ch in "'\"":
            quote = ch
            continue
        out.append(ch)
    bare = "".join(out)
    return not any(op in bare for op in OPERATORS)


def program_of(tokens: list[str]) -> tuple[int, str, str]:
    """(index of the program token, program, subcommand), skipping a leading `sudo`."""
    i = 1 if tokens and tokens[0] == "sudo" else 0
    prog = tokens[i] if i < len(tokens) else ""
    sub = tokens[i + 1] if i + 1 < len(tokens) and not tokens[i + 1].startswith("-") else ""
    return i, prog, sub


def seed_for(base_seed: int, probe_id: str, transform: str) -> int:
    digest = hashlib.sha256(f"{base_seed}:{probe_id}:{transform}".encode()).digest()
    return int.from_bytes(digest[:4], "big")


def base_item(probe: Probe) -> Variant:
    return Variant.from_dict(
        {
            "id": f"{probe.id}/base",
            "probe_id": probe.id,
            "parent_id": None,
            "relation_class": "base",
            "transform": "identity",
            "expected": "reference",
            "tool": probe.tool,
            "call": probe.call,
            "policy_id": probe.policy_id,
            "policy_rendering": CANONICAL_RENDERING,
            "context": "",
            "option_names": dict(DEFAULT_OPTION_NAMES),
        }
    )


def make_variant(probe: Probe, cls: str, transform: str, n: int, seed: int, change: Change) -> Variant:
    return Variant.from_dict(
        {
            "id": f"{probe.id}/{transform}/{n}",
            "probe_id": probe.id,
            "parent_id": f"{probe.id}/base",
            "relation_class": cls,
            "transform": transform,
            "expected": EXPECTED[cls],
            "tool": change.get("tool", probe.tool),
            "call": change.get("call", probe.call),
            "policy_id": probe.policy_id,
            "policy_rendering": change.get("policy_rendering", CANONICAL_RENDERING),
            "context": change.get("context", ""),
            "policy_text": change.get("policy_text"),
            "option_names": change.get("option_names", dict(DEFAULT_OPTION_NAMES)),
            "seed": seed,
        }
    )


def with_command(probe: Probe, command: str) -> Change:
    return {"call": {**probe.call, "command": command}}
