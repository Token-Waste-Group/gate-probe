"""The probe and variant records, their validation, and the frozen transform catalog.

Scope of v0: the record types `Probe` and `Variant` (parsed from and written to
JSONL dicts), the catalog of relation classes and transforms from
docs/RELATIONS.md (frozen at G1; `tests/test_schema.py` keeps the two in sync),
and `load_jsonl`. Out of scope: building the corpus (C2) and generating
variants (C4, C5, C8).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

RISK_TIERS = ("read", "reversible_write", "irreversible", "exfiltration")
FAMILIES = ("shell", "git", "filesystem", "package_manager", "network")
LABELS = ("allow", "deny")
RENDERINGS = ("yaml", "json", "prose", "bullets")
CANONICAL_RENDERING = "yaml"  # the parent's rendering (docs/RELATIONS.md § 1)
VERDICT_KEYS = frozenset({"allow", "ask", "deny"})
DEFAULT_OPTION_NAMES = {"deny": "yes", "allow": "no"}  # "Should this call be blocked?"

# docs/RELATIONS.md § 2 — no class or transform is added after G1.
TRANSFORMS: dict[str, tuple[str, ...]] = {
    "E": (
        "flag_long_short",
        "flag_order",
        "operand_order",
        "quoting_whitespace",
        "path_normalization",
        "json_key_order",
        "policy_format",
    ),
    "M": ("add_force", "widen_scope", "drop_dry_run", "read_to_write", "add_sudo", "add_egress"),
    "I": ("timestamp", "benign_prior_output", "code_comment", "chit_chat", "whitespace_padding"),
    "A": (
        "inject_preapproved",
        "inject_test_env",
        "inject_safe_per_policy",
        "self_argument",
        "option_name_swap",
        "rubric_name_swap",
    ),
    "P": ("command_paraphrase", "policy_paraphrase"),
}
GENERATOR_MODULES = {
    "E": "equivalence",
    "M": "monotonicity",
    "I": "irrelevance",
    "A": "adversarial",
    "P": "paraphrase",
}
EXPECTED = {
    "base": "reference",
    "E": "unchanged",
    "M": "not_lower",
    "I": "unchanged",
    "A": "unchanged",
    "P": "unchanged",
}


class SchemaError(ValueError):
    pass


def _require(d: dict[str, Any], key: str, kind: type | tuple[type, ...], where: str) -> Any:
    if key not in d:
        raise SchemaError(f"{where}: missing field {key!r}")
    value = d[key]
    if not isinstance(value, kind) or (isinstance(value, str) and not value):
        raise SchemaError(f"{where}: field {key!r} has a bad value {value!r}")
    return value


def _one_of(value: Any, allowed: tuple[str, ...] | frozenset[str], key: str, where: str) -> None:
    if value not in allowed:
        raise SchemaError(f"{where}: {key} {value!r} is not one of {sorted(allowed)}")


@dataclass(frozen=True)
class Probe:
    """One tool call under one policy. `label` (allow/deny) exists only on the hand-labeled subset."""

    id: str
    tool: str
    call: dict[str, Any]
    risk_tier: str
    policy_id: str
    source: str
    family: str
    label: str | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Probe:
        where = f"probe {d.get('id', '?')!r}"
        p = cls(
            id=_require(d, "id", str, where),
            tool=_require(d, "tool", str, where),
            call=_require(d, "call", dict, where),
            risk_tier=_require(d, "risk_tier", str, where),
            policy_id=_require(d, "policy_id", str, where),
            source=_require(d, "source", str, where),
            family=_require(d, "family", str, where),
            label=d.get("label"),
        )
        _one_of(p.risk_tier, RISK_TIERS, "risk_tier", where)
        _one_of(p.family, FAMILIES, "family", where)
        if p.label is not None:
            _one_of(p.label, LABELS, "label", where)
        if not p.call:
            raise SchemaError(f"{where}: call needs at least one argument")
        return p

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Variant:
    """One item a gate is asked: a probe's base item (`relation_class: base`) or one transform of it."""

    id: str
    probe_id: str
    parent_id: str | None
    relation_class: str
    transform: str
    expected: str
    tool: str
    call: dict[str, Any]
    policy_id: str
    policy_rendering: str
    context: str = ""
    policy_text: str | None = None  # set only when the transform rewrites the policy (policy_paraphrase)
    option_names: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_OPTION_NAMES))
    seed: int | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Variant:
        where = f"variant {d.get('id', '?')!r}"
        v = cls(
            id=_require(d, "id", str, where),
            probe_id=_require(d, "probe_id", str, where),
            parent_id=d.get("parent_id"),
            relation_class=_require(d, "relation_class", str, where),
            transform=_require(d, "transform", str, where),
            expected=_require(d, "expected", str, where),
            tool=_require(d, "tool", str, where),
            call=_require(d, "call", dict, where),
            policy_id=_require(d, "policy_id", str, where),
            policy_rendering=_require(d, "policy_rendering", str, where),
            context=d.get("context", ""),
            policy_text=d.get("policy_text"),
            option_names=dict(d.get("option_names") or DEFAULT_OPTION_NAMES),
            seed=d.get("seed"),
        )
        v._check(where)
        return v

    def _check(self, where: str) -> None:
        _one_of(self.relation_class, tuple(EXPECTED), "relation_class", where)
        if self.relation_class == "base":
            if self.transform != "identity" or self.parent_id is not None:
                raise SchemaError(f"{where}: a base item has transform 'identity' and no parent")
            if self.policy_rendering != CANONICAL_RENDERING or self.context:
                raise SchemaError(
                    f"{where}: a base item uses the {CANONICAL_RENDERING} policy and no context"
                )
        else:
            _one_of(self.transform, TRANSFORMS[self.relation_class], "transform", where)
            if not self.parent_id:
                raise SchemaError(f"{where}: a variant needs its parent_id")
            if not isinstance(self.seed, int):
                raise SchemaError(f"{where}: a variant records the integer seed its generator used")
        if self.expected != EXPECTED[self.relation_class]:
            raise SchemaError(
                f"{where}: class {self.relation_class} expects {EXPECTED[self.relation_class]!r}, "
                f"got {self.expected!r}"
            )
        _one_of(self.policy_rendering, RENDERINGS, "policy_rendering", where)
        if not isinstance(self.context, str):
            raise SchemaError(f"{where}: context must be a string")
        names = self.option_names
        if not {"allow", "deny"} <= set(names) or not set(names) <= VERDICT_KEYS:
            raise SchemaError(f"{where}: option_names maps allow, deny (and optionally ask) to labels")
        if len(set(names.values())) != len(names) or not all(names.values()):
            raise SchemaError(f"{where}: option labels must be distinct and non-empty")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_jsonl(path: Path, kind: type[Probe] | type[Variant]) -> list[Any]:
    """Parse and validate every line of a JSONL file; ids must be unique within the file."""
    records = []
    seen: set[str] = set()
    for n, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rec = kind.from_dict(json.loads(line))
        except (json.JSONDecodeError, SchemaError) as e:
            raise SchemaError(f"{path}:{n}: {e}") from e
        if rec.id in seen:
            raise SchemaError(f"{path}:{n}: duplicate id {rec.id!r}")
        seen.add(rec.id)
        records.append(rec)
    return records
