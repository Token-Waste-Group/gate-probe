"""Tests for the Claude Code PreToolUse hook (fake gate, temp cache; no network).

Scope of v0: call reduction, cache-first answers and --replay-only, advisory
output, --enforce denying but never approving, fragility warnings from scored
results, cached refusals, and the never-break-the-agent contract (errors become
a message, exit 0, keys redacted). Out of scope: the OpenCode plugin (I7).
"""

from __future__ import annotations

import io
import json
from dataclasses import asdict
from types import SimpleNamespace

from gateprobe.gates.base import GateRequest, ToolCall
from gateprobe.gates.fake import FakeGate
from gateprobe.hook.claude_code import fragile, main, reduce_call, run
from gateprobe.runner.cache import Cache, cache_key

EVENT = {
    "hook_event_name": "PreToolUse",
    "tool_name": "Bash",
    "tool_input": {"command": "rm -rf ./build", "description": "clean", "timeout": 120000},
}


class Counting(FakeGate):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.calls = 0

    def decide(self, request):
        self.calls += 1
        return super().decide(request)


def seed_cache(cache: Cache, gate, request: GateRequest, entry: dict) -> None:
    cache.put(
        cache_key(gate.gate_id, gate.model_id, getattr(gate, "mode", ""), gate.request_bytes(request), 1),
        entry,
    )


def test_reduce_call_keeps_corpus_arguments_only():
    assert reduce_call("Bash", EVENT["tool_input"]) == ToolCall("Bash", {"command": "rm -rf ./build"})
    assert reduce_call("Write", {"file_path": "a", "content": "b", "x": 1}).args == {
        "file_path": "a",
        "content": "b",
    }


def test_cached_answer_is_used_and_no_call_is_made(tmp_path):
    gate, cache = Counting(overrides={"rm -rf": 0.9}), Cache(tmp_path)
    req = GateRequest("policy", reduce_call("Bash", EVENT["tool_input"]), policy_id="p")
    seed_cache(cache, gate, req, {"decision": asdict(gate.decide(req))})
    gate.calls = 0
    out = run(EVENT, gate, "policy", "p", cache, replay_only=True)
    assert gate.calls == 0 and out["systemMessage"].endswith("DENY, p_block 0.90 [cached]")
    assert "hookSpecificOutput" not in out  # advisory by default


def test_replay_only_miss_and_live_call(tmp_path):
    gate, cache = Counting(overrides={"rm -rf": 0.2}), Cache(tmp_path)
    miss = run(EVENT, gate, "policy", "p", cache, replay_only=True)
    assert "not in the cache" in miss["systemMessage"] and gate.calls == 0
    live = run(EVENT, gate, "policy", "p", cache)
    assert "ALLOW, p_block 0.20 [live]" in live["systemMessage"] and gate.calls == 1
    assert list(tmp_path.iterdir()) == []  # the hook never writes the cache


def test_enforce_denies_but_never_approves(tmp_path):
    deny = run(EVENT, Counting(overrides={"rm -rf": 0.9}), "policy", "p", Cache(tmp_path), enforce=True)
    assert deny["hookSpecificOutput"]["permissionDecision"] == "deny"
    allow = run(EVENT, Counting(overrides={"rm -rf": 0.1}), "policy", "p", Cache(tmp_path), enforce=True)
    assert "hookSpecificOutput" not in allow


def test_fragility_warnings_from_scored_results(tmp_path):
    results = tmp_path / "res"
    results.mkdir()
    (results / "transforms.csv").write_text(
        "gate_id,class,transform,label,excess,excess_lo,excess_hi\n"
        "fake,E,flag_long_short,positive,0.12,0.05,0.19\n"
        "fake,M,add_sudo,neutral,0.01,-0.02,0.04\n"
        "other,E,flag_long_short,positive,0.5,0.4,0.6\n",
        encoding="utf-8",
    )
    call = ToolCall("Bash", {"command": "sudo rm --recursive ./build"})
    assert fragile(results, "fake", call) == ["flag_long_short: +0.12 flips above the floor [0.05, 0.19]"]
    event = {"tool_name": "Bash", "tool_input": {"command": "sudo rm --recursive ./build"}}
    out = run(event, Counting(), "policy", "p", Cache(tmp_path / "c"), results=results)
    assert "⚠ fragile here: flag_long_short" in out["systemMessage"]


def test_cached_refusal(tmp_path):
    gate, cache = Counting(), Cache(tmp_path)
    req = GateRequest("policy", reduce_call("Bash", EVENT["tool_input"]), policy_id="p")
    seed_cache(cache, gate, req, {"refusal": {}, "message": "declined"})
    assert "refused" in run(EVENT, gate, "policy", "p", cache)["systemMessage"] and gate.calls == 0


def test_main_never_breaks_the_agent_and_redacts():
    args = SimpleNamespace(
        gates_config="/nonexistent/sk-or-v1-0123456789abcdef.yaml",
        run_config="x",
        gate="jev",
        policy="p",
        rendering="yaml",
        results=None,
        replay_only=True,
        enforce=False,
    )
    out = io.StringIO()
    assert main(args, stdin=io.StringIO(json.dumps(EVENT)), stdout=out) == 0
    msg = json.loads(out.getvalue())["systemMessage"]
    assert msg.startswith("GateProbe hook error") and "sk-or-v1-0123456789abcdef" not in msg
    out = io.StringIO()
    assert main(args, stdin=io.StringIO("not json"), stdout=out) == 0
