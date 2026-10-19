"""The Claude Code `PreToolUse` hook: ask the gate under test about the agent's real tool call.

Protocol (code.claude.com/docs/en/hooks): Claude Code sends the call as JSON
on stdin (`tool_name`, `tool_input`, ...); a JSON object on stdout with
`systemMessage` is shown to the user; `hookSpecificOutput.permissionDecision`
set to `deny` blocks the call. This hook is **advisory by default**: it shows
the gate's verdict and p_block, plus a warning when the call has a feature
whose transform the gate failed in a scored run (`--results`). `--enforce`
lets it *deny* when the gate denies; it never auto-approves, because an
untested gate approving calls on its own is what GateProbe argues against.

The call is reduced to the arguments the corpus uses (Claude Code adds fields
such as `description`), so a demo call hits the same cache key as the run that
scored it. The cache is read first (repeat 1), and the hook never writes to it.
`--replay-only` never calls a live API. Any failure becomes a message and exit
code 0, so the hook never breaks the agent. Key-like strings are redacted.

Scope of v0: Claude Code's Bash, Read, Write, Edit and WebFetch tools. Out of
scope: the OpenCode plugin (I7, stretch).
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any, TextIO

from gateprobe.gates.base import GateDecision, GateRequest, ToolCall
from gateprobe.report.html import redact

ROOT = Path(__file__).resolve().parents[3]
KEEP = {
    "Bash": ("command",),
    "Read": ("file_path",),
    "Write": ("file_path", "content"),
    "Edit": ("file_path", "old_string", "new_string"),
    "WebFetch": ("url", "prompt"),
}
# Features visible in a live call -> the transform whose results warn about them.
FEATURES = {
    "flag_long_short": lambda c: " --" in c,
    "quoting_whitespace": lambda c: "'" in c or '"' in c or "  " in c.strip(),
    "path_normalization": lambda c: "$PWD/" in c,
    "code_comment": lambda c: " #" in c,
    "self_argument": lambda c: " #" in c and any(w in c.lower() for w in ("safe", "allowed", "harmless")),
    "add_sudo": lambda c: c.lstrip().startswith("sudo "),
    "add_egress": lambda c: "| sh" in c or "| bash" in c,
}


def reduce_call(tool: str, tool_input: dict[str, Any]) -> ToolCall:
    keep = KEEP.get(tool)
    args = {k: tool_input[k] for k in keep if k in tool_input} if keep else dict(tool_input)
    return ToolCall(tool, args)


def fragile(results: Path | None, gate_id: str, call: ToolCall) -> list[str]:
    """Positive transforms of this gate (from results/<name>/transforms.csv) whose feature the call has."""
    path = results / "transforms.csv" if results else None
    if path is None or not path.exists() or call.tool != "Bash":
        return []
    cmd = str(call.args.get("command", ""))
    out = []
    with path.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            t = r.get("transform", "")
            if (
                r.get("gate_id") == gate_id
                and r.get("label") == "positive"
                and t in FEATURES
                and FEATURES[t](cmd)
            ):
                out.append(
                    f"{t}: +{float(r['excess']):.2f} flips above the floor [{float(r['excess_lo']):.2f}, "
                    f"{float(r['excess_hi']):.2f}]"
                )
    return out


def decide(gate: Any, request: GateRequest, cache: Any, replay_only: bool) -> tuple[GateDecision | None, str]:
    from gateprobe.runner.cache import cache_key

    key = cache_key(gate.gate_id, gate.model_id, getattr(gate, "mode", ""), gate.request_bytes(request), 1)
    entry = cache.get(key)
    if entry and "decision" in entry:
        return GateDecision(**entry["decision"]), "cached"
    if entry and "refusal" in entry:
        return None, "the gate refused this call when it was scored"
    if replay_only:
        return None, "not in the cache (--replay-only: no live call)"
    return gate.decide(request), "live"


def run(
    event: dict[str, Any],
    gate: Any,
    policy_text: str,
    policy_id: str,
    cache: Any,
    results: Path | None = None,
    replay_only: bool = False,
    enforce: bool = False,
) -> dict[str, Any]:
    call = reduce_call(event.get("tool_name", ""), event.get("tool_input") or {})
    request = GateRequest(policy=policy_text, call=call, policy_id=policy_id)
    decision, source = decide(gate, request, cache, replay_only)
    head = f"GateProbe · {gate.gate_id} ({gate.model_id})"
    if decision is None:
        return {"systemMessage": redact(f"{head}: no verdict — {source}")}
    lines = [f"{head}: {decision.verdict.upper()}, p_block {decision.p_block:.2f} [{source}]"]
    lines += [f"⚠ fragile here: {w}" for w in fragile(results, gate.gate_id, call)]
    out: dict[str, Any] = {"systemMessage": redact("\n".join(lines))}
    if enforce and decision.verdict == "deny":
        out["hookSpecificOutput"] = {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": redact(
                f"{gate.gate_id} denies this call (p_block {decision.p_block:.2f})"
            ),
        }
    return out


def main(args: Any, stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout) -> int:
    try:
        from gateprobe.config import load_gates, load_run
        from gateprobe.corpus.render import FILES
        from gateprobe.env import load_dotenv
        from gateprobe.gates.factory import make_gate
        from gateprobe.runner.cache import Cache

        event = json.loads(stdin.read() or "{}")
        gates = load_gates(args.gates_config)
        run_cfg = load_run(args.run_config)
        if not args.replay_only:
            load_dotenv()
        gate = make_gate(gates[args.gate])
        policy = (ROOT / "policies" / args.policy / FILES[args.rendering]).read_text(encoding="utf-8")
        out = run(
            event,
            gate,
            policy,
            args.policy,
            Cache(ROOT / run_cfg.cache_dir),
            results=args.results,
            replay_only=args.replay_only,
            enforce=args.enforce,
        )
    except Exception as e:  # the hook must never break the agent
        out = {"systemMessage": redact(f"GateProbe hook error: {type(e).__name__}: {e}")}
    stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
    return 0
