---
description: Pick up the next unclaimed step in docs/PLAN.md (optionally in one lane, e.g. `/continue C`) and drive it to a merged PR (the autonomous loop).
argument-hint: "[lane letter(s), e.g. C or R,X]"
---

You are advancing the GateProbe demo (ICSE 2027 Tool Demonstration track)
autonomously. Follow this loop **exactly**. Read `CLAUDE.md`,
`gateprobe_plan.md`, `docs/AUTONOMY.md`, `STATUS.md`, and every `memory/*.md`
first — the hard invariants there (frozen scope, human decision points,
pre-registered scoring, floors and intervals, pinned models, $ caps, the G3
results freeze) are non-negotiable. The goal is the submitted demo: **Fri 23
Oct evening**, hard stop **Sat 24 Oct 13:59 CEST** (AoE).

Lane requested: `$ARGUMENTS` (empty = any lane). Lanes: C corpus and
relations, R adapters/runner/analysis, X runs, I integrations/packaging,
W paper/video; the shared lanes S (skeleton) and G (decision packets) come
along with every lane. Pass it to `claim.py` as `--lane <lane>`. If your lane
has nothing eligible, say so and offer to take the first eligible step of any
lane (a dry run without `--lane`) — don't take it unasked.

**Cadence (strict):** do **exactly one** step per `/continue`. Announce your plan
*before* you start, and at the end report what you did, say what you'd do next,
and **ask the human before continuing** — never auto-advance to the next step.
Stop and report immediately if you hit a blocker.

**Plan changes need a human.** If the work suggests new, split, or re-sequenced
steps, **propose it and wait for confirmation** before editing the step set in
`docs/PLAN.md`. Atomic status updates via `claim.py`/`mark.py` are not plan
changes. **G1, G2, G3 and every fallback trigger in the plan's risk table are
human decisions** — the loop reports the numbers, it never decides.

### 0. Sync & bootstrap
```
export PATH="$HOME/.local/bin:$PATH"
git switch main && git pull --rebase origin main
bash scripts/bootstrap.sh        # idempotent: uv, venv, deps; warns on missing gh/.env/docker/latexmk
```
If `bootstrap.sh` warns that `gh` is unauthenticated, stop and ask the human to
run `gh auth login` (the loop needs it to open/merge PRs).

### 1. Claim the next step (race-safe, hardware-aware)
First peek: `python3 scripts/claim.py --dry-run [--lane <lane>]`. It prints the
step it would take plus any `[HUMAN]` steps waiting on a person — mention those
in your report. If the step needs what this machine lacks (`[API: OpenRouter]`
without `OPENROUTER_API_KEY`; `[GPU: H100]` without the VPN and the `d.dgx`
ssh alias), re-peek with `--skip-tag API` / `--skip-tag GPU`; if nothing fits,
report which step is next and where it should run, then stop. Otherwise claim
with the same flags:
```
python3 scripts/claim.py [--lane <lane>] [--skip-tag <TAG>]
```
- Prints `CLAIMED <id>` + the step block, or `NONE` (then stop — nothing eligible).
- `claim.py` already handles the parallel-agent race: it commits the claim to
  `main` and pushes; if another agent won the race it re-syncs and re-picks.
  Trust its output — the step it printed is yours.
- If you claimed something you can't actually run, release it:
  `python3 scripts/mark.py <id> todo "needs <hw/key>; this machine lacks it"`
  and stop for the human.
- **Then announce** (before any code): post 2–4 lines — the claimed step id and
  how you'll satisfy its `done-when`.

### 2. Branch & implement
```
git switch -c feat/<id>-<short-slug>
```
- Implement **exactly** the step's `done-when`, nothing more. Keep the diff
  small and in scope. Match the codebase style in `CLAUDE.md`.
- **Add or extend tests** under `tests/` for any code change. Tests never touch
  the network — use recorded fixtures or fake endpoints.
- Never violate the hard invariants: scope frozen (no relation class after G1);
  E/M/I/A deterministic and seeded, P always separate from E; scoring exactly
  as pre-registered in `docs/RELATIONS.md`; floor subtracted, repeats + Wilson
  95% intervals on every number; model ids pinned in `configs/gates.yaml`;
  cache key includes the repeat index; every row logs git hash + config hash +
  gate + model + repeat; API paths respect the $ cap and log spend; after G3 no
  new rows in `results/`; no secrets or heavy artifacts in git.
- **`[GPU: H100]` steps:** follow `memory/reference-dgx-usage.md` to the letter
  (GPU #7 only, compose only, files only under the storage dir, never stop
  `kaluzhnaya_stale_runner`, clean up after).
- **X steps (runs):** write `docs/experiments/<id>-<slug>.md` with `status:
  planned`, the decision rule copied from `docs/RELATIONS.md`, the config and
  the $ cap; **commit and push it before launching the run**; then run; then
  commit the data and the result (positive / neutral / negative per relation —
  a negative is a finding, not a failure to hide) as a separate commit. Update
  `STATUS.md` (one line for today) in the same PR.
- **`[GATE]` steps:** write `docs/gates/<id>-<slug>.md` — the recorded numbers,
  the state of every step, the triggers that fired, the options the plan names,
  your recommendation — and make no decision yourself.

### 3. Gate
```
bash scripts/check.sh > /tmp/gate.log 2>&1; echo "gate exit: $?"; tail -5 /tmp/gate.log
```
Fix until the exit status is 0 — read the exit status, never a pipe's
(`memory/lesson-gate-exit-status.md`). Run `uv run ruff format <your changed
files>` before committing so the format gate stays green.

### 4. Commit, PR, auto-merge
```
git add -A && git commit -m "<imperative subject>"   # + Claude Co-Authored-By trailer
git push -u origin feat/<id>-<short-slug>
gh pr create --fill --base main
python3 scripts/mark.py <id> "in_review (#<pr-number>)"
gh pr checks <pr-number> --watch
gh pr view <pr-number> --json statusCheckRollup -q '.statusCheckRollup[0].conclusion'   # must be SUCCESS
gh pr merge --squash --delete-branch <pr-number>     # X steps: --merge instead of --squash
gh pr view <pr-number> --json state -q .state        # must be MERGED
```
- **Auto-merge only when the gate is green locally and CI says SUCCESS.**
- **If the merge reports a conflict:** `git fetch origin main && git rebase origin/main`,
  resolve the conflict, re-run the gate, `git push --force-with-lease`, retry the merge.
- **If genuinely stuck** (unresolvable conflict, failing upstream, ambiguous
  spec, a fallback trigger fired):
  `python3 scripts/mark.py <id> blocked "<one-line reason>"` and **stop,
  reporting to the human**. Do not force or hack around a blocker.

### 5. Close out
```
git switch main && git pull --rebase origin main
python3 scripts/mark.py <id> done
```
**`[GATE]` steps don't close as done:** run
`python3 scripts/mark.py <id> blocked "awaiting human decision — docs/gates/<file>"`
instead; the humans record the decision in `STATUS.md` and mark it done.
Optionally propose refinements to `docs/PLAN.md` (new/split/re-sequenced steps)
— but apply them only after human confirmation, using the same claim-style
commit-and-push so concurrent agents stay consistent.

### 6. Report & ask
Summarize what merged (step id, PR #, what changed, key numbers with repeats
and intervals if it was a run), the `[HUMAN]` steps now waiting on someone,
what you'd do next (the next eligible step in this lane and which machine it
needs), and **ask whether to continue. Do not auto-proceed** to the next step —
wait for the human's «продолжи».
