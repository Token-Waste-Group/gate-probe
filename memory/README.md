# `memory/` — team-shared Claude knowledge

This directory is **committed, PR-reviewed agent memory**: durable lessons,
constraints, and feedback that every contributor's Claude Code session should
load. It exists because per-user Claude memory (under `~/.claude/...`) is
private to one machine — when a colleague's Claude learns something important,
the rest of the team's agents never see it. Committing it here fixes that.

It never ships publicly: the I6 release branch leaves `memory/` out (it names
internal hosts and storage paths).

## Protocol

- **Read everything in `memory/*.md` at session start.** `CLAUDE.md` instructs
  agents to do this.
- **One fact per file.** Use a kebab-case name and a short type tag in the body
  (`feedback`, `lesson`, `reference`, `decision`). Link related entries with
  `[[name]]`.
- **Promote, don't hoard.** When you learn a durable, generalizable lesson in a
  session (a Decisions API quirk, a flaky relation, a reviewer-facing
  constraint), write it here and include it in your PR so the team inherits
  it. Volatile, task-local notes stay in your private `~/.claude` memory.
- **Changes go through PR review** like any other repo content — these files
  steer every agent, so they deserve scrutiny.

## Current entries

- `decision-autonomy-loop.md` — how the `/continue` loop, lanes, `[GATE]` and
  `[HUMAN]` steps work, and its non-negotiable rules.
- `decision-research-discipline.md` — frozen scope, human decision points,
  pre-registered oracle-free scoring, noise floors, provenance, budget.
- `decision-llm-routing.md` — which gate goes through which route (Decisions
  API, vLLM judge on the H100, local rules) and the $ caps.
- `reference-dgx-usage.md` — the machines (RTX boxes, H100 GPU #7, V100s), their
  access paths and the rules that keep our access.
- `lesson-gate-exit-status.md` — read the gate's exit status, not a pipe's;
  merge only on CI `SUCCESS`; mark done only when `MERGED`.
- `lesson-preregistration-git-trail.md` — planned report before the run;
  merge X-step PRs with `--merge`.
- `lesson-zero-floor-gates.md` — with f = δ = 0 the S and M-p secondaries count
  any movement; report verdict-level counts, never re-label.
- `lesson-flip-does-not-say-which-verdict.md` — a flip proves a contradiction;
  "wrongly approved" needs the policy to deny the call.
- `lesson-read-top-transforms.md` — read `top_transforms.csv` after every
  analysis; it is how generator bugs surface.
- `lesson-colima-shares-home-only.md` — colima mounts only `~`; a mount from
  elsewhere arrives empty and every replay misses.
- `lesson-strace-breaks-sudo.md` — setuid is ignored under ptrace; report
  "both failed, nothing changed" pairs apart.
- `lesson-subset-scores-reuse-the-frozen-floor.md` — re-score subsets with the
  full run's floor, and check the "all" subset reproduces the frozen row.
