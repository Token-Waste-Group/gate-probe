# CLAUDE.md — working agreement for Claude Code in this repo

This file is auto-loaded into every Claude Code session. It is the single
source of truth for how agents (and humans) work here. **Read it fully before
changing anything.** The frozen proposal — tool design, relations, validation
plan, schedule, risks, decision points — is `gateprobe_plan.md` (repo root).
For team-shared lessons, read everything under `memory/` at session start. The
daily log and decision-point outcomes live in `STATUS.md`.

## What this project is (north star)

**GateProbe** for the **ICSE 2027 Tool Demonstration and Data Showcase track**:
a metamorphic testing harness for the permission gates that approve or deny
coding-agent tool calls. A gate (a typed decision model such as Jev 1.14 via
the OpenRouter Decisions API, an LLM-judge prompt, or a rule set) takes a
policy, a tool call and context and returns allow/deny with a probability.
GateProbe rewrites those inputs under relations with known expected outcomes —
**E**quivalence, **M**onotonicity, **I**rrelevance, **A**dversarial, and the
weaker **P**araphrase class — and reports violations per relation and per gate,
with the test–retest noise floor subtracted. No ground truth is needed.

Deliverables: the `gateprobe` CLI + Docker image; adapters `decisions`,
`judge`, `rules`, `http`; a ~300-call corpus under authority-repo policies; an
HTML report and a CI mode; a Claude Code `PreToolUse` hook for the live demo; a
key-free replay mode; a 4-page paper; a 3–5-minute video.

**Deadline:** submit **Fri 23 Oct 2026 evening**; hard stop **Sat 24 Oct 13:59
CEST** (AoE). Day 0 = Mon 19 Oct. RQ1 invariance · RQ2 monotonicity ·
RQ3 adversarial · RQ4 cost. Either sign of each result ships — a clean
"E flips sit at the floor" is a finding; the plan then leads with M and A.

## Hard invariants — do NOT break these

These protect the validity of the demo's claims. A change that violates one is
wrong even if it runs. If a task seems to require breaking one, **stop and
raise it** instead of working around it.

1. **Scope is frozen** (`gateprobe_plan.md`): five relation classes, four
   gates, RQ1–RQ4, three figures. **No new relation class after G1**
   (Mon 19 18:00) — it goes to the paper's future work. Stretch items (P
   sandbox validation, OpenCode plugin, PolicyForge) only after G2 records full
   scope.
2. **Decision points are human decisions.** G1 (spec freeze), G2 (go/no-go:
   full / reduced / pivot to ToolSense), G3 (results freeze) and every fallback
   trigger in the plan's risk table (Jev unreachable 12 h, < 200 probes,
   hook flaky on camera) are decided by a human from recorded numbers. The loop
   reports and recommends; it never decides.
3. **Oracle-free by construction.** E, M, I, A generators are deterministic
   (seeded, seed stored) and need no labels; every variant carries parent id,
   class, transform and expected outcome. P (LLM paraphrase) is generated,
   labeled as P, and **always reported separately from E**.
4. **Scoring rules are pre-registered** in `docs/RELATIONS.md` (C1) before any
   run: violation predicates, the floor, "flip rate above the floor", the
   threshold-band rule. Never relax a predicate after seeing results. The ~60
   hand labels serve the calibration figure only — never to tune generators,
   prompts or thresholds.
5. **Noise is subtracted, never ignored.** Each gate's test–retest floor comes
   from identical repeats (default 3; 5 on a gate whose floor exceeds 10%).
   **Every reported number states its repeats and a Wilson 95% interval.**
6. **Models are pinned.** Every gate's model id lives in `configs/gates.yaml`
   (`typesafe/jev-1.14`, never a floating alias); the judge's served model,
   revision and dtype are recorded; the judge prompt is frozen once R4 merges.
7. **The response cache is the source of truth and the replay mode.** Every
   gate response is stored content-addressed; the key includes the repeat
   index, so repeats are real calls; replay runs with no key. Never delete or
   rewrite cache entries behind a reported run.
8. **Provenance on every row.** Every run row logs git hash, config hash, gate
   id, pinned model id, repeat index, timestamp. Every experiment = one CLI
   invocation + one config; no notebook-only results.
9. **Budget.** Every API-calling path reads a $ cap from config and logs spend
   to `results/spend.csv`. The whole evaluation stays under $20 of API calls;
   check GPT-6 Luna Decisions pricing before any run and cap it at $20.
10. **Results freeze at G3** (Thu 22 12:00): afterwards `results/` gets no new
    rows, the paper and the video use only those numbers, and only W-lane steps
    and packaging fixes that change no number land.
11. **Never commit or show secrets or heavy artifacts.** Keys live only in
    `.env` (git-ignored, read-denied to agents) and must never reach a log,
    report, hook output, or the screen in the video. `cache/` and `runs/` are
    git-ignored; `results/` CSVs are append-only and committed.
12. **Negative results are committed, never dropped.** See the Results rule.
13. **Prior work and format.** The authority and supersession preprints are
    cited neutrally; no tool details are lifted from them and their systematic
    findings stay for the planned A\* paper. The paper is 4 pages including
    references, `\documentclass[10pt,conference]{IEEEtran}`, no compsoc,
    margins and spacing untouched, single-anonymous (author names in).
14. **The public artifact is a cleaned release** (step I6): no agent pipeline,
    `memory/`, `STATUS.md`, internal hostnames or storage paths. This dev repo
    stays private.

## Repository map

Paths marked with a step id don't exist yet; that step creates them.

```
gateprobe_plan.md        # the frozen proposal + sprint plan — read before code
STATUS.md                # one line per day + every decision-point outcome
docs/PLAN.md             # step ledger driving the autonomous loop
docs/AUTONOMY.md         # loop protocol; .claude/commands/continue.md is the runbook
docs/RELATIONS.md        # (C1) relation spec + pre-registered scoring rules
docs/CORPUS.md           # (C2) corpus datasheet
docs/experiments/        # committed run reports (incl. negatives)
docs/gates/              # (G1–G3) decision packets for the humans
configs/                 # (S1) gates.yaml (pinned ids), run.yaml, corpus.yaml, judge_prompt.md
probes/  policies/       # (C2, C3) corpus JSONL; policies in YAML/JSON/prose/bullets
variants/                # (C4, C5, C8) generated variants, deterministic
src/gateprobe/           # (S1) corpus/ relations/ gates/ runner/ analysis/ report/ hook/
integrations/            # (I2) Claude Code PreToolUse hook
deploy/vllm-judge/       # (R5) compose file for the judge on the H100
cache/  runs/            # git-ignored: response cache (= replay bundle) and run JSONL
results/                 # distilled CSVs, append-only, committed
paper/  video/           # (W1, W6) IEEEtran LaTeX; storyboard, voice-over, captions
scripts/                 # loop mechanics + thin wrappers
```

## Code style

- Python ≥ 3.11; `from __future__ import annotations`; modern typing
  (`X | None`, `list[...]`, no `Optional`/`List`).
- **Ruff is the single source of truth.** Run `ruff check .` and
  `ruff format .`. Config in `pyproject.toml` (line-length 110; rules
  `E,F,I,UP,B,SIM`).
- Every module docstring states its purpose *and* a "Scope of v0 / out of
  scope" note.
- **Tests never touch the network.** Adapters are tested on recorded fixtures
  or fake endpoints; live calls happen only in `[API: …]` steps and runs.
- Keep dependencies lean — no new heavy dependency without discussion in the
  PR. `pip install gateprobe` must stay light.

## Collaboration workflow (multiple agents, one repo)

- Four workstreams, one owner each (named at G1): C corpus/relations (P1),
  R + X adapters/runner/analysis/runs (P2), I integrations/packaging (P3),
  W paper/video (P4). `/continue C` keeps an agent in its lane.
- **One step → one short-lived branch** off the latest `main`
  (`feat/… | fix/… | docs/… | chore/…`). **Never commit to `main`** except the
  claim/mark ledger commits made by the scripts.
- `git pull --rebase origin main` before starting and before pushing.
- **Keep PRs small and single-purpose** so parallel agents don't collide.
- **Before every commit, the local gate is mandatory:** `bash scripts/check.sh`
  (`ruff check . && ruff format --check . && pytest -q`). CI mirrors it.
- Imperative commit subjects; include the Claude `Co-Authored-By:` trailer on
  agent-made commits.
- Update `STATUS.md` and any touched docs in the **same** PR.

## Shared memory protocol

- `memory/*.md` is **team-shared, committed, PR-reviewed** agent knowledge.
  **Read it at session start.** One fact per file, kebab-case names, a short
  type tag (`feedback`, `lesson`, `reference`, `decision`).
- When you learn a durable, generalizable lesson (an API quirk, a flaky
  relation, a reviewer-facing constraint), **promote it to `memory/` via a PR**
  so every teammate's agent inherits it. Per-user `~/.claude` memory is private
  scratch, not a substitute.

## Running & verifying

```bash
bash scripts/bootstrap.sh              # uv + venv + deps
cp .env.example .env                   # then set OPENROUTER_API_KEY
bash scripts/check.sh                  # the gate
```

Gate runs are API- and/or GPU-bound and cost money — run them deliberately in
their `[API: …]` / `[GPU: …]` step (see `docs/AUTONOMY.md` § Hardware-aware
claiming), never as casual checks. Replay (`--replay`) is free and key-free.

## Autonomous research loop

This repo advances via a self-driving loop. The plan and claim ledger is
`docs/PLAN.md`; the runbook is the `/continue` slash command; the full protocol
is `docs/AUTONOMY.md`. To make progress, run `/continue` (or say «продолжи»),
optionally with a lane letter: Claude claims the next eligible step, implements
its `done-when`, runs the gate, opens a PR, and **auto-merges when green**,
then marks the step done.

Conventions that keep parallel agents safe:
- **Never hand-edit step statuses** in `docs/PLAN.md` — `scripts/claim.py` and
  `scripts/mark.py` update them atomically (git push is the lock; the loser
  re-picks).
- One claimed step per agent; stay within its scope. **Plan changes (new /
  split / re-sequenced steps) need human confirmation** — propose, don't
  self-edit.
- **Hardware-aware claiming:** don't claim `[GPU: …]` / `[API: OpenRouter]`
  steps on a machine that can't run them (`claim.py --skip-tag GPU`); release
  a mis-claim with `mark.py <id> todo "<reason>"`. `[HUMAN]` steps are never
  claimed; `[GATE]` steps end `blocked` until a human decides.
- **Cadence:** one step per `/continue`; announce before you start; then report
  and **ask before continuing** (no auto-advance).
- **Blocked > forced:** unresolvable conflicts, ambiguity, or a fallback
  trigger → `scripts/mark.py <id> blocked` and stop for a human.

## Results & experiments

Empirical results are committed, never discarded. Every X step writes a report
to `docs/experiments/<id>-<slug>.md` — **including negative or failed
results** (a fail is a finding; silently dropping it is forbidden). The report
carries: question, method + exact reproduce command, the **pre-registered
decision rule** (from `docs/RELATIONS.md`), the data with repeats and
intervals, a result classified **positive / neutral / negative** per relation,
and the conclusion. Raw artifacts (`cache/`, `runs/`) stay git-ignored and are
shipped as the replay bundle; commit only the report + distilled numbers. A
step that makes an empirical claim is **not `done` until its report is
committed**. See `docs/experiments/README.md`.
