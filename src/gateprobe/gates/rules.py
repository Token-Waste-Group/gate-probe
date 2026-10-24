"""The `rules` adapter: a deterministic baseline gate evaluating Claude Code-style permission patterns.

Semantics follow the Claude Code permissions docs (code.claude.com/docs/en/permissions):
- deny rules are checked before allow rules, and the first match decides; an
  allow rule never carves an exception out of a deny rule;
- `Bash(...)` patterns match the command text as written; `*` matches any
  text, and a trailing ` *` (or `:*`) also matches the bare command; compound
  commands are split on `&&`, `||`, `;`, `|`, `|&`, `&` and newlines, so an
  allow needs every part matched, while one matching part triggers a deny;
- `Read(...)` / `Edit(...)` paths use gitignore-style anchors: `//abs`, `~/home`,
  `/project-root`, `./cwd` (or a path with a slash), and a bare name at any
  depth; `*` stays within one path segment, `**` crosses them; `Edit` rules
  cover the Write tool too; Read deny rules also cover the files that `cat`,
  `head`, `tail`, `less` and `more` read inside Bash, and Edit deny rules
  cover the files `tee` writes;
- `WebFetch(domain:host)` matches that exact host; a bare `Tool` matches every
  call of that tool.
Unlike Claude Code, which prompts the user, an unmatched call is denied: the
policies are default-deny. p_block is 1.0 for deny and 0.0 for allow.

Scope of v0: allow and deny lists per policy (`policies/<id>/rules.yaml`), the
semantics above, a fixed project root (`/workspace/project`) and home
(`/home/agent`). Out of scope: ask rules, process wrappers, redirects, and
other tools' parameter rules.
"""

from __future__ import annotations

import hashlib
import json
import posixpath
import re
from functools import cache
from pathlib import Path
from typing import Any

import yaml

from gateprobe.gates.base import GateAdapter, GateDecision, GateRequest

PROJECT = "/workspace/project"
HOME = "/home/agent"
POLICIES = Path(__file__).resolve().parents[3] / "policies"
SEPARATORS = ("&&", "||", "|&", ";", "|", "&", "\n")
READ_COMMANDS = {"cat", "head", "tail", "less", "more"}
RULE = re.compile(r"^(\w+)(?:\((.*)\))?$", re.DOTALL)


class RulesError(ValueError):
    pass


def split_compound(command: str) -> list[str]:
    """Split on shell separators outside quotes; empty parts are dropped."""
    parts, buf, quote, i = [], [], None, 0
    while i < len(command):
        ch = command[i]
        if quote:
            buf.append(ch)
            quote = None if ch == quote else quote
            i += 1
            continue
        if ch in "'\"":
            quote = ch
            buf.append(ch)
            i += 1
            continue
        sep = next((s for s in SEPARATORS if command.startswith(s, i)), None)
        if sep:
            parts.append("".join(buf))
            buf = []
            i += len(sep)
            continue
        buf.append(ch)
        i += 1
    parts.append("".join(buf))
    return [p.strip() for p in parts if p.strip()]


def bash_pattern(spec: str) -> re.Pattern[str]:
    if spec.endswith(":*"):
        spec = spec[:-2] + " *"
    if spec.endswith(" *") and spec.count("*") == 1:
        return re.compile(re.escape(spec[:-2]) + r"(?: .*)?", re.DOTALL)
    return re.compile(".*".join(re.escape(part) for part in spec.split("*")), re.DOTALL)


def resolve_path(path: str) -> str:
    """Where a call's path points, with the agent in the project root."""
    if path == "~" or path.startswith("~/"):
        return posixpath.normpath(HOME + path[1:])
    if path.startswith("$HOME/"):
        return posixpath.normpath(HOME + path[5:])
    if path.startswith("/"):
        return posixpath.normpath(path)
    return posixpath.normpath(posixpath.join(PROJECT, path))


def _glob(pattern: str) -> str:
    out, i = [], 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return "".join(out)


def path_pattern(spec: str) -> re.Pattern[str]:
    if spec.startswith("//"):
        anchored = spec[1:]
    elif spec.startswith("~/"):
        anchored = HOME + spec[1:]
    elif spec.startswith("/"):
        anchored = PROJECT + spec
    elif spec.startswith("./") or "/" in spec.rstrip("/"):
        anchored = PROJECT + "/" + spec.removeprefix("./")
    else:  # a bare name matches at any depth under the project
        return re.compile(re.escape(PROJECT) + "/(?:.*/)?" + _glob(spec))
    return re.compile(_glob(anchored))


def parse_rule(rule: str) -> tuple[str, str | None]:
    m = RULE.match(rule.strip())
    if not m:
        raise RulesError(f"not a permission rule: {rule!r}")
    return m.group(1), m.group(2)


def _operands(subcommand: str) -> list[str]:
    tokens = subcommand.split()
    return [t.strip("'\"") for t in tokens[1:] if not t.startswith("-")]


def _matches(rule: str, tool: str, args: dict[str, Any], sub: str | None = None) -> bool:
    rtool, spec = parse_rule(rule)
    file_tool = "Edit" if tool in ("Edit", "Write") else tool
    if rtool != file_tool:
        return False
    if spec is None:
        return True
    if tool == "Bash":
        return bool(bash_pattern(spec).fullmatch(sub if sub is not None else args.get("command", "")))
    if tool in ("Read", "Edit", "Write"):
        return bool(path_pattern(spec).fullmatch(resolve_path(str(args.get("file_path", "")))))
    if tool == "WebFetch" and spec.startswith("domain:"):
        host = re.sub(r"^\w+://", "", str(args.get("url", ""))).split("/")[0]
        return host == spec[len("domain:") :]
    return False


def evaluate(rules: dict[str, list[str]], tool: str, args: dict[str, Any]) -> tuple[str, str | None]:
    """(verdict, the rule that decided it, or None when the default deny applied)."""
    deny, allow = rules.get("deny", []), rules.get("allow", [])
    if tool == "Bash":
        subs = split_compound(str(args.get("command", "")))
        for sub in subs:
            for r in deny:
                if _matches(r, tool, args, sub):
                    return "deny", r
            if sub.split()[0] in READ_COMMANDS | {"tee"}:
                file_tool = "Edit" if sub.split()[0] == "tee" else "Read"
                for path in _operands(sub):
                    for r in deny:
                        if _matches(r, file_tool, {"file_path": path}):
                            return "deny", r
        matched = []
        for sub in subs:
            hit = next((r for r in allow if _matches(r, tool, args, sub)), None)
            if hit is None:
                return "deny", None
            matched.append(hit)
        return ("allow", " + ".join(matched)) if matched else ("deny", None)
    for r in deny:
        if _matches(r, tool, args):
            return "deny", r
    for r in allow:
        if _matches(r, tool, args):
            return "allow", r
    return "deny", None


@cache
def _load(path: Path) -> tuple[dict[str, list[str]], str]:
    text = path.read_text(encoding="utf-8")
    data = yaml.safe_load(text) or {}
    rules = {"allow": list(data.get("allow", [])), "deny": list(data.get("deny", []))}
    for r in rules["allow"] + rules["deny"]:
        parse_rule(r)
    return rules, hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


class RulesGate(GateAdapter):
    mode = "rules"

    def __init__(
        self, gate_id: str = "rules", model_id: str = "rules-v0", policies_dir: Path = POLICIES
    ) -> None:
        self.gate_id, self.model_id, self.policies_dir = gate_id, model_id, Path(policies_dir)

    def rules_for(self, policy_id: str) -> tuple[dict[str, list[str]], str]:
        path = self.policies_dir / policy_id / "rules.yaml"
        if not policy_id or not path.exists():
            raise RulesError(f"no rule set for policy {policy_id!r} at {path}")
        return _load(path)

    def request_bytes(self, request: GateRequest) -> bytes:
        # The rule gate reads the policy id, never the policy text; the rule-set digest
        # is in the key, so editing a rule set can't serve stale answers from the cache.
        _, digest = self.rules_for(request.policy_id)
        fields = [request.policy_id, digest, request.call.tool, request.call.args]
        return json.dumps(fields).encode("utf-8")

    def decide(self, request: GateRequest) -> GateDecision:
        rules, digest = self.rules_for(request.policy_id)
        verdict, rule = evaluate(rules, request.call.tool, request.call.args)
        return GateDecision(
            verdict=verdict,
            p_block=1.0 if verdict == "deny" else 0.0,
            raw={"matched_rule": rule, "default_deny": rule is None, "rules_digest": digest},
            gate_id=self.gate_id,
            model_id=self.model_id,
            latency_ms=0.0,
            cost_usd=0.0,
        )
