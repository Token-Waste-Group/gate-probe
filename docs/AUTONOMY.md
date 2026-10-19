# Autonomous research loop

This repo can drive itself toward the finished ICSE 2027 demo submission, one
reviewed step at a time, with several Claude Code agents (one per workstream,
on the laptops and driving the H100) working in parallel without colliding.
This is the human-readable spec; the executable runbook is the `/continue`
slash command (`.claude/commands/continue.md`), and the mechanics live in
`scripts/`.

## The UX

```
git clone …/gate-probe && cd gate-probe
claude                       # start Claude Code
> /continue                  # or «продолжи»; `/continue C` stays in lane C
```

Claude picks the next unclaimed step from `docs/PLAN.md` (in your lane, if you
gave one), implements it, opens a PR, and **auto-merges when the gate is
green**, then stops (or loops if you ask).

## Source of truth: `docs/PLAN.md`

`docs/PLAN.md` is both the roadmap and the **claim ledger**. Each step is a
block with `status / owner / claimed_at / deps / source / done-when`. The
`status/owner/claimed_at` fields mark who is working on what. **Don't hand-edit
statuses while the loop runs** — `scripts/claim.py` and `scripts/mark.py`
update them atomically.

Steps are grouped by sprint day (Mon 19 – Fri 23), and file order is priority
order: `claim.py` takes the first eligible step. The plan may evolve toward
realizing `gateprobe_plan.md` (the frozen proposal), but **changes to the step
set need a human**: the loop *proposes* new / split / re-sequenced steps and
applies them only after confirmation. The loop never self-edits the plan's
structure — it only updates step **statuses** atomically (claim / in_review /
done / blocked / todo-release). `cut` is a human-only status.

## Lanes: four workstreams, four agents

The step id's letter prefix is its lane: **S** shared skeleton, **C** corpus
and relations (P1), **R** adapters/runner/analysis/figures and **X** runs (P2),
**I** integrations and packaging (P3), **W** paper and video (P4), **G**
decision points, **H** human-only tasks. Each owner's agent runs
`/continue <lane>` (→ `claim.py --lane <lane>`) so it doesn't pick another
workstream's step. The shared lanes **S** and **G** pass every lane filter:
whichever agent is free first builds the skeleton or writes a decision packet,
and G1/G3 sit right after the steps that unlock them so they're taken at once.
With no lane, an agent takes the first eligible step of any lane — useful when
its own lane is idle. Dependencies cross lanes freely.

## Cadence & human checkpoints

`/continue` runs **exactly one step**, with a human checkpoint on each side:

1. **Announce first.** After claiming, the agent states (2–4 lines) which step
   it took and how it will satisfy the `done-when` — *before* writing code.
2. **Implement → gate → PR → auto-merge** (below).
3. **Report & ask.** The agent summarizes what merged, says what it would do
   next, and **asks whether to continue** — it does not auto-advance. Progress
   resumes only when a human says «продолжи».

## How parallel agents stay out of each other's way

Git is the arbiter (an atomic ref update wins). To claim a step, `claim.py`:

1. `git fetch origin main && git reset --hard origin/main` (sync to the truth),
2. picks the first `todo` step whose `deps` are all `done` or `cut`, that is
   in the requested lane, not `[HUMAN]`, and carries none of the skipped tags,
3. flips it to `claimed` (with owner + timestamp), commits, and **pushes to main**,
4. if the push is **rejected** (someone else pushed first), discards the local
   claim, re-syncs, and re-picks — looping until its push lands or nothing is left.

So two agents that grab the same step at the same moment can't both win: exactly
one push lands; the other re-picks the next eligible step. The claim is visible
to everyone on the next `git pull`.

## Decision points (`[GATE]`) and human tasks (`[HUMAN]`)

The plan has three hard decision points — **G1** Mon 19 18:00 (relation spec
and corpus schema frozen), **G2** Wed 21 18:00 (go/no-go: full / reduced /
pivot to ToolSense), **G3** Thu 22 12:00 (results frozen). For each, the loop:

1. claims the G step once its deps are done,
2. writes `docs/gates/<id>-<slug>.md` — the recorded numbers, the state of
   every step, the triggers that fired, the options the plan names, and a
   recommendation,
3. merges that packet like any PR, then runs
   `mark.py <id> blocked "awaiting human decision — docs/gates/<file>"` and stops.

The humans decide, record the decision in `STATUS.md`, mark `cut` whatever left
scope, and run `mark.py <id> done`. Everything downstream waits on that.

`[HUMAN]` steps (HotCRP, labels, recording, publishing, submitting) are never
claimed by `claim.py`; `claim.py --dry-run` lists the eligible ones as
"waiting on a human" so every agent's report can remind the team. A human does
the task and runs `mark.py <id> done`.

The plan's other fallback triggers (Decisions API down 12 h → Clef and judge
only; < 200 probes Tuesday night → ship 200; hook flaky → CLI-only video) are
human calls too: the agent that hits one marks its step `blocked` with the
numbers and stops.

## Hardware-aware claiming

This project spans: laptops (code, tests, corpus, paper), the OpenRouter
Decisions API (`[API: OpenRouter]`: Jev and the other decision models), and
the H100 (`[GPU: H100]`: the vLLM judge; the paraphrase model, which may also
fit the RTX boxes). The H100 is **driven from a laptop over ssh** with docker
compose, so a `[GPU: H100]` step runs on any machine with the VPN up and the
`d.dgx` alias — not only on a machine with a local GPU.

**Before claiming, check whether this machine can actually run the next eligible
step** (`claim.py --dry-run`). If it can't (no `OPENROUTER_API_KEY` with
credit, no VPN/ssh to d.dgx), re-run with `--skip-tag API` / `--skip-tag GPU`
to find the next step it can do; if nothing fits, report which step is next and
where it should run. If you discover the mismatch only *after* claiming,
`scripts/mark.py <id> todo "needs <hw>, this machine lacks it"` to release it.
Never sit on a claim you cannot execute — on a five-day sprint, a stuck claim
is schedule damage.

**How each machine is actually used** (access paths, the GPU #7-only and
compose-only rules on the H100, storage under `/data/storage/kaluzhnaya_jhub/`,
never stopping `kaluzhnaya_stale_runner`) is codified in
`memory/reference-dgx-usage.md` — read it before implementing any `[GPU: …]`
step. Model routing and budget: `memory/decision-llm-routing.md`.

## Merge policy

- Work happens on a per-step branch `feat/<id>-<slug>`; **never commit to
  `main`** except the tiny claim/mark ledger commits the scripts make.
- **Auto-merge requires the gate to be green:** `ruff check .` +
  `ruff format --check .` + `pytest -q` (`scripts/check.sh`). Format your
  changed files with `uv run ruff format <paths>` before committing. The same
  gate runs in CI via `.github/workflows/gate.yml` on every PR into `main` and
  every push to `main`.
- **Read the gate's exit status, not a pipe's** (`memory/lesson-gate-exit-status.md`):
  never `check.sh | tail && …`. Merge only when the PR's CI conclusion is
  `SUCCESS`; mark a step done only after the PR state is `MERGED`.
- **Code PRs squash** (`gh pr merge --squash --delete-branch`). **Experiment
  PRs (X steps) merge with `--merge`** so the planned-report commit stays
  visibly ahead of the results commit
  (`memory/lesson-preregistration-git-trail.md`).
- **Conflicts:** rebase the branch on `origin/main`, resolve, re-gate, re-merge.
- **Blocked:** anything unresolvable (bad conflict, failing upstream, ambiguous
  spec, a fallback trigger) → `scripts/mark.py <id> blocked "<reason>"` and
  **stop for a human**. The loop never forces a merge, never hacks around a
  blocker, and **never decides G1, G2, G3 or a fallback itself**.

## Prerequisites (per machine)

`scripts/bootstrap.sh` is idempotent and sets up most of it:

- **uv** — installed if missing; creates `.venv` (Python 3.11, as in CI);
  `uv pip install -e ".[dev]"`.
- **gh** — must be authenticated (`gh auth login`) for PR + auto-merge.
  Bootstrap warns if not.
- **`.env`** — `OPENROUTER_API_KEY` is required for `[API: OpenRouter]` steps;
  `HF_READ_TOKEN` for pulling the judge weights. Code/test/paper steps need
  neither. Copy `.env.example`.
- **docker** for the image steps (I4, I5); **latexmk** for the paper (W steps).
- **VPN + `d.dgx` ssh alias** for `[GPU: H100]` steps.

## Safety / guardrails

- One claimed step per agent at a time; stay within the step's `done-when` scope.
- Never force-push `main`; never commit secrets or heavy artifacts (`cache/`,
  `runs/` are git-ignored; `.env` is deny-listed in `.claude/settings.json`).
- Every code change ships tests; tests never touch the network; the gate is
  mandatory before any merge.
- Respect the hard invariants in `CLAUDE.md` and `memory/` — frozen scope,
  human decision points, pre-registered scoring, floors and intervals, pinned
  models, cache provenance, $ caps, the G3 results freeze.
- Nothing outward-facing (making a repo public, pushing an image, uploading the
  video, submitting) happens in an agent step — those are `[HUMAN]` steps.

## Scripts

| Script | Does |
|---|---|
| `scripts/bootstrap.sh` | idempotent env setup; warns on missing prereqs |
| `scripts/agent_id.sh` | stable claim owner id (`name@host`) |
| `scripts/check.sh` | the gate: ruff check + ruff format --check + pytest |
| `scripts/claim.py` | atomically claim the next eligible step (race-safe; `--lane`, `--skip-tag`, `--dry-run`) |
| `scripts/mark.py` | set a step's status on main (`in_review` / `done` / `blocked` / `todo` / `cut`) |
| `.github/workflows/gate.yml` | runs `scripts/check.sh` on every PR / push to main |

## Results rule

Runs commit their findings. Every X step writes a report under
`docs/experiments/<id>-<slug>.md` and commits it — **negative and failed results
included** (a fail is a finding, never silently dropped). Each report states the
question, method + exact reproduce command, the **pre-registered decision rule**
(copied from `docs/RELATIONS.md` before the run), the data with repeats and 95%
intervals, a `positive | neutral | negative` result per relation, and the
conclusion. Raw artifacts (`cache/`, `runs/`) stay git-ignored and ship as the
replay bundle; only the report + distilled numbers land in git (`results/` CSVs
are append-only). An empirical-claim step is not `done` until its report exists.
Full convention: `docs/experiments/README.md`.

`STATUS.md` (repo root) is the complementary **daily log**: one line per day +
every decision-point outcome, updated each evening.
