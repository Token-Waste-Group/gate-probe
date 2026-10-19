# Claude Code hook

`gateprobe hook` is a Claude Code `PreToolUse` hook. Before each tool call
it asks the gate under test what it would decide, then shows the verdict and
the block probability in the session. It also warns when the call has a
feature (long flags, quoting, `$PWD/`, a comment, `sudo`, `| sh`) whose
transform that gate failed in a scored run.

```
GateProbe · jev (typesafe/jev-1.14-20261014): DENY, p_block 0.96 [cached]
⚠ fragile here: flag_long_short: +0.12 flips above the floor [0.05, 0.19]
```

**Advisory by default.** The hook never changes what Claude Code does. With
`--enforce` it *denies* calls the gate denies. It never approves anything:
an untested gate auto-approving calls is the problem GateProbe exists to test.

## Install

1. Bootstrap the repo (`bash scripts/bootstrap.sh`).
2. Copy the `hooks` block from `settings.example.json` into
   `.claude/settings.json` of the project where you'll run Claude Code. Replace
   `/path/to/gate-probe` with the absolute path of this repo.
3. Choose the gate (`--gate`, a name in `configs/gates.yaml`), the policy
   (`--policy`, a directory under `policies/`) and its rendering
   (`--rendering`, default `yaml`).

## Options

| Flag | Effect |
|---|---|
| `--replay-only` | answer only from the response cache; never call an API and need no key (the demo uses this) |
| `--results results/<name>/` | the `gateprobe analyze` output whose positive transforms drive the warnings |
| `--enforce` | deny the call when the gate denies it (never approve) |

The hook reduces each call to the arguments the corpus uses (Claude Code adds
fields such as `description`), so a demo call hits the same cache entry as the
run that scored it. It reads the cache and never writes to it. Every failure
becomes a message with exit code 0, so the hook can't break the session.
Anything shaped like an API key is redacted from its output.

## Try it without Claude Code

```bash
echo '{"tool_name": "Bash", "tool_input": {"command": "cat .env", "description": "x"}}' \
  | uv run gateprobe hook --gate jev --policy read-only-review --replay-only
```
