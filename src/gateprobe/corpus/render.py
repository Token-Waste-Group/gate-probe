"""Render each policy in `configs/policies.yaml` as YAML, JSON, prose and a bullet list.

Scope of v0: deterministic renderers from the one structured source, so the four
renderings carry the same rules (the `policy_format` E transform depends on
that), and a parser back from the YAML and JSON renderings to the rule set. All
four state the same semantics: default deny, and deny overrides allow. Out of
scope: the rule gate's pattern sets (R3) and model-written paraphrases (C8).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from gateprobe.corpus.schema import RENDERINGS

SEMANTICS = "Anything not allowed is denied, and a deny rule always overrides an allow rule."
FILES = {
    "yaml": "policy.yaml",
    "json": "policy.json",
    "prose": "policy.prose.md",
    "bullets": "policy.bullets.md",
}


class PolicyError(ValueError):
    pass


def load_source(path: Path) -> dict[str, Any]:
    src = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    for p in src["policies"]:
        for r in p["rules"]:
            if r["effect"] not in ("allow", "deny"):
                raise PolicyError(f"{p['id']}: effect {r['effect']!r}")
            if r["action"] not in src["actions"] or r["scope"] not in src["scopes"]:
                raise PolicyError(f"{p['id']}: unknown action or scope in {r}")
    return src


def _phrase(src: dict[str, Any], rule: dict[str, str]) -> str:
    scope = "" if rule["scope"] == "anywhere" else " " + src["scopes"][rule["scope"]]
    return src["actions"][rule["action"]] + scope


def structured(src: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    """The machine-readable form behind the YAML and JSON renderings, glossary included."""
    used_actions = sorted({r["action"] for r in policy["rules"]})
    used_scopes = sorted({r["scope"] for r in policy["rules"]})
    return {
        "policy": policy["id"],
        "title": policy["title"],
        "description": policy["description"],
        "semantics": SEMANTICS,
        "rules": [{k: r[k] for k in ("effect", "action", "scope")} for r in policy["rules"]],
        "definitions": {
            "actions": {a: src["actions"][a] for a in used_actions},
            "scopes": {s: src["scopes"][s] for s in used_scopes},
        },
    }


def render(src: dict[str, Any], policy: dict[str, Any], fmt: str) -> str:
    if fmt == "yaml":
        return yaml.safe_dump(structured(src, policy), sort_keys=False, allow_unicode=True, width=100)
    if fmt == "json":
        return json.dumps(structured(src, policy), indent=2, ensure_ascii=False) + "\n"
    allowed = [_phrase(src, r) for r in policy["rules"] if r["effect"] == "allow"]
    denied = [_phrase(src, r) for r in policy["rules"] if r["effect"] == "deny"]
    if fmt == "prose":
        return (
            f"Policy: {policy['title']}. {policy['description']} "
            f"The agent may {_join(allowed)}. "
            f"The agent must not {_join(denied)}. {SEMANTICS}\n"
        )
    if fmt == "bullets":
        lines = [f"Policy: {policy['title']}", policy["description"], "", "Allowed:"]
        lines += [f"- {a}" for a in allowed] + ["", "Not allowed:"] + [f"- {d}" for d in denied]
        return "\n".join(lines + ["", f"Rule: {SEMANTICS}"]) + "\n"
    raise PolicyError(f"unknown rendering {fmt!r}; expected one of {RENDERINGS}")


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else "; ".join(items[:-1]) + "; or " + items[-1]


def parse_rules(text: str, fmt: str) -> list[dict[str, str]]:
    """The rule list back out of a YAML or JSON rendering."""
    data = yaml.safe_load(text) if fmt == "yaml" else json.loads(text)
    return data["rules"]


def render_all(src: dict[str, Any]) -> dict[str, str]:
    """Every rendering of every policy, keyed by its path relative to policies/."""
    return {f"{p['id']}/{FILES[fmt]}": render(src, p, fmt) for p in src["policies"] for fmt in RENDERINGS}
