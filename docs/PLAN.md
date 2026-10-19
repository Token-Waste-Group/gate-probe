# GateProbe — sprint plan & claim ledger

This is the **single living source of truth** for the road to the ICSE 2027
Tool Demonstration submission: *GateProbe, a metamorphic testing harness for
coding-agent permission gates*. It is both the roadmap (ordered,
dependency-aware steps) and the **claim ledger** that lets several Claude Code
agents (one per workstream, on the laptops and against the H100) work in
parallel without colliding. The loop that drives it is `/continue`; the full
protocol is in `docs/AUTONOMY.md`; the frozen proposal behind every step is
`gateprobe_plan.md` (repo root — read it before touching code).

**How to work this file:** don't hand-edit statuses during the loop — the
scripts do it atomically. To advance the project, run `/continue` (optionally
`/continue C` to stay in your lane), which does **exactly one step** then asks
before continuing. The plan may evolve toward realizing `gateprobe_plan.md`, but
**changes to the step set (adding / splitting / re-sequencing steps) must be
proposed to a human and confirmed before they are applied** — the loop never
self-edits the plan's structure.

**Deadline:** submit **Fri 23 Oct 2026, evening**; hard stop **Sat 24 Oct 13:59
CEST / 14:59 MSK** (Fri 23 Oct AoE). Day 0 = Mon 19 Oct. Sat 24 is buffer only:
nothing new after 12:00 CEST.
**Frozen scope:** `gateprobe_plan.md` — relation classes E, M, I, A, P; RQ1–RQ4;
four gates, plus the Claude Opus 5.5 judge the humans added on 2026-10-19
(R8, X7); three figures. No new relation classes after G1.
**Decision points (human):** G1 Mon 19 18:00 spec freeze · G2 Wed 21 18:00
go/no-go (full / reduced / pivot to ToolSense) · G3 Thu 22 12:00 results freeze.
After G3 only the paper and the video move.
**Out of scope unless a human adds a step:** PolicyForge, anything the plan
lists as future work.

## Step format (machine-parsed by scripts/claim.py & scripts/mark.py)

```
### <id> — <title> [TAG: …]
- status: todo | claimed | in_review | done | blocked | cut
- owner: —                      (set by claim.py)
- claimed_at: —                 (set by claim.py)
- deps: <id> <id> | —           (eligible only when every dep is done or cut)
- source: <which plan section / RQ / day motivates it>
- done-when: <concrete, checkable acceptance criteria>
```

`cut` is terminal and human-only: a step retired by a decision (e.g. a
`[STRETCH]` step after a reduced-scope G2). Its dependents stop waiting for it.

**Lanes** (the id's letter prefix; `claim.py --lane C` keeps an agent in one;
the shared lanes S and G pass every lane filter, so whichever agent is free
first takes the skeleton and the decision packets):

| Lane | Workstream | Owner |
|---|---|---|
| E | loop bootstrap | — |
| S | shared skeleton | whoever is free first |
| C | Corpus and relations | P1 |
| R | Adapters, runner, analysis, figures | P2 |
| X | Experiment runs (RQ1–RQ4) | P2, on whichever machine has the API key / H100 |
| I | Integrations and packaging | P3 |
| W | Paper and video | P4 |
| G | Decision points — the loop prepares the packet, the humans decide | all four |
| H | Human-only tasks (accounts, labels, recording, publishing, submission) | named at G1 |

**Tags** in the title (`claim.py --skip-tag GPU` skips what this machine can't run):

| Tag | Means |
|---|---|
| `[API: OpenRouter]` | needs `OPENROUTER_API_KEY` with credit (Decisions API) |
| `[API: Anthropic]` | needs `ANTHROPIC_API_KEY` (the Claude judge; ~$200 budget) |
| `[GPU: H100]` | drives d.dgx GPU #7 over ssh — VPN up; read `memory/reference-dgx-usage.md` |
| `[GPU: H100 or RTX]` | an open model small enough for the RTX boxes also works |
| `[GATE]` | the loop writes `docs/gates/<id>-<slug>.md`, merges it, then marks the step `blocked "awaiting human decision"`; a human records the decision in `STATUS.md` and runs `mark.py <id> done` |
| `[HUMAN]` | never auto-claimed; listed by `claim.py --dry-run` as waiting; the human does it and runs `mark.py <id> done` |
| `[STRETCH]` | only after G2 records full scope; otherwise a human marks it `cut` |

---

## E0 — Bootstrap the autonomous loop

### E0.1 — Plan ledger, /continue runbook, scripts, env
- status: done
- owner: bootstrap
- claimed_at: 2026-10-19
- deps: —
- source: user request 2026-10-19 (mirror the latent-underspecification-research loop)
- done-when: gateprobe_plan.md (frozen proposal) + CLAUDE.md + docs/PLAN.md + docs/AUTONOMY.md + docs/experiments/README.md + .claude/commands/continue.md + scripts/{bootstrap,agent_id,check}.sh + scripts/{claim,mark}.py + tests/{test_smoke,test_claim}.py + .github/workflows/gate.yml merged; memory/ seeded; STATUS.md started; gate green.

---

## Day 0 — Mon 19 Oct: scope frozen, skeleton, 150 probes, pinned Jev answers, judge prompt, paper skeleton

### S1 — Package skeleton, adapter contract, CLI entry point, configs
- status: done
- owner: jrzkaminski@Jerzy-Pro.local
- claimed_at: 2026-10-19T16:52:35Z
- deps: E0.1
- source: gateprobe_plan.md § Tool design; Mon DoD "repo skeleton"
- done-when: `src/gateprobe/` subpackages `corpus`, `relations`, `gates`, `runner`, `analysis`, `report`, `hook` exist with module stubs whose docstrings state purpose + v0 scope; `gateprobe/gates/base.py` defines the adapter contract every gate implements (policy, tool call, context → verdict ∈ {allow, ask, deny}, p_block, raw response, gate id, pinned model id, latency, cost) plus a deterministic `fake` adapter for tests; a `gateprobe` console script with `expand | run | report | ci | replay` subcommands (`--help` works; unimplemented ones exit non-zero with a clear message); `configs/gates.yaml` (Jev pinned as `typesafe/jev-1.14`, judge model + endpoint as config keys, rules gate; no floating aliases) and `configs/run.yaml` (repeats 3, seed, per-gate $ caps, retry/backoff); `probes/`, `policies/`, `variants/`, `results/` tracked with .gitkeep, `cache/` and `runs/` git-ignored; tests for the CLI and config loading.

### C1 — Relation spec, scoring rules, corpus schema (frozen at G1)
- status: done
- owner: jrzkaminski@Jerzy-Pro.local
- claimed_at: 2026-10-19T17:12:15Z
- deps: S1
- source: gateprobe_plan.md § Metamorphic relations, § Validation plan; decision point 1
- done-when: `docs/RELATIONS.md` lists every transform of classes E, M, I, A, P from the plan's table — and nothing beyond those five classes — with its generator name, its expected outcome and the exact violation predicate (E and I: the verdict changes, or |Δp_block| exceeds the gate's floor; M: p_block drops by more than the floor, and deny → allow is always a violation; A: the verdict changes, with the mean p_block shift reported; P: as E, reported separately); the scoring rules RQ1–RQ3 will use (floor definition from identical repeats, "flip rate above the floor", Wilson 95% intervals, when a relation counts as violated for a gate, the threshold-band rule) are written here **before any run** — this is the pre-registration the X reports cite; `gateprobe/corpus/schema.py` defines and validates the probe record (`id, tool, call, risk_tier ∈ {read, reversible_write, irreversible, exfiltration}, policy_id, source, label?`) and the variant record (`id, parent_id, relation_class, transform, expected, call, policy_rendering, context`), with unit tests.

### G1 — Decision point 1: relation spec and corpus schema frozen (Mon 19, 18:00) [GATE]
- status: blocked
- note: awaiting human decision — docs/gates/g1-spec-freeze.md
- owner: jrzkaminski@Jerzy-Pro.local
- claimed_at: 2026-10-19T17:15:29Z
- deps: C1
- source: gateprobe_plan.md § Risks and decision points (1); § Assumptions and open questions
- done-when: the loop writes `docs/gates/g1-spec-freeze.md` — the C1 relation list and scoring rules, the schema, and the plan's open questions with its proposed answers (workstream owners; primary Jev question — Noul for the flip analysis, Choice for the hook; second decision model — Clef, Mercury Decide, or both if the budget check passes; Claude Code only in the video, or OpenCode too) — then `mark.py G1 blocked "awaiting human decision"`. The four reviewers record the freeze and the answers in STATUS.md and run `mark.py G1 done`. After G1 no relation class is added; new ideas go to the paper's future work.

### C2 — Probe corpus v0: 150 tool calls
- status: done
- owner: jrzkaminski@Jerzy-Pro.local
- claimed_at: 2026-10-19T17:18:25Z
- deps: C1
- source: gateprobe_plan.md § Tool design (Probe corpus); Mon DoD "150 probes"
- done-when: ≥ 150 probes in `probes/*.jsonl` that validate against the C1 schema, spanning shell, git, filesystem, package managers and network, with every risk tier represented; every probe has a `source` — a public agent-trace reference with its license, or `template:<name>`; templated synthesis is a committed deterministic script (`scripts/build_corpus.py` + `configs/corpus.yaml`, seed recorded); `docs/CORPUS.md` datasheet with counts per tool family × risk tier × source (also in the PR description); a schema test runs over the committed files.

### C3 — Policies in four renderings (YAML, JSON, prose, bullets)
- status: done
- owner: jrzkaminski@Jerzy-Pro.local
- claimed_at: 2026-10-19T17:22:19Z
- deps: S1
- source: gateprobe_plan.md § Tool design (Policies); assumption 3
- done-when: each policy the corpus will use exists under `policies/<policy_id>/` in YAML, JSON, prose and bullet-list renderings generated from one structured source; renderings are reused from the authority repo (`../authority`, `src/authinv/render/`) where a matching renderer exists, and the rest come from `gateprobe/corpus/render.py`; `policies/README.md` records the authority commit hash and which renderings were reused vs new; a test parses the YAML and JSON renderings back to the same rule set; nothing beyond the policies themselves is taken from the authority work, which is unpublished and is never cited or mentioned in the paper (human rule, 2026-10-19).

### R1 — Decisions API adapter, pinned Jev 1.14 [API: OpenRouter]
- status: done
- owner: jrzkaminski@Jerzy-Pro.local
- claimed_at: 2026-10-19T17:23:54Z
- deps: S1
- source: gateprobe_plan.md § Tool design (Gate adapters); Mon DoD "Decisions client returning pinned Jev answers"; open question 2
- done-when: `gateprobe/gates/decisions.py` implements the S1 contract against OpenRouter `POST /api/alpha/decisions` in Noul mode ("Should this call be blocked under the policy?") and Choice mode (allow / ask / deny), mode chosen in config; the model id comes from `configs/gates.yaml` and the adapter refuses an unpinned id; unit tests run on recorded fixtures with no network; one live call per mode against `typesafe/jev-1.14`, with its request id and cost, in the PR description; the key is read from the environment and never logged.

### R2 — Runner, content-addressed cache, replay, spend cap
- status: done
- owner: jrzkaminski@Jerzy-Pro.local
- claimed_at: 2026-10-19T17:29:03Z
- deps: S1
- source: gateprobe_plan.md § Tool design (Runner); § Budget and compute
- done-when: `gateprobe run` sends variants × repeats (default 3, from config) through any adapter with retries and exponential backoff; every response lands in a content-addressed cache `cache/<sha256>.json` keyed on (gate id, pinned model id, mode, exact request bytes, repeat index), so repeats are real repeated calls and never cache hits of one another; `--replay` serves only from the cache, needs no key, and fails loudly on a miss; the per-gate $ cap from config is checked before each call and spend is appended to `results/spend.csv` (gate, model, tokens, USD, run id); every run JSONL row records git hash, config hash, gate id, model id, repeat index and timestamp; tests with the fake adapter cover cache hit/miss, replay miss, cap stop and retry.

### R3 — Rule gate baseline (Claude Code-style allow/deny patterns)
- status: in_review (#9)
- owner: jrzkaminski@Jerzy-Pro.local
- claimed_at: 2026-10-19T17:33:47Z
- deps: S1 C3
- source: gateprobe_plan.md § Validation plan (rule gate)
- done-when: `gateprobe/gates/rules.py` evaluates Claude Code-style permission patterns (e.g. `Bash(git push:*)`, `Read(./.env)`) with deny-over-allow precedence and p_block ∈ {0, 1}, deterministic; one rule set per policy at `policies/<policy_id>/rules.yaml`, hand-written to match the policy (stated as such in `policies/README.md`); unit tests on pattern semantics (prefix match, precedence, unmatched calls).

### R4 — Judge adapter and the fixed judge prompt
- status: todo
- owner: —
- claimed_at: —
- deps: S1
- source: gateprobe_plan.md § Tool design (judge); Mon DoD "judge prompt fixed"
- done-when: `gateprobe/gates/judge.py` calls any OpenAI-compatible chat endpoint (base URL and model from config, key from the environment when one is needed) at temperature 0; the judge prompt is committed at `configs/judge_prompt.md` and is frozen once this step merges (changing it needs a human); p_block comes from the verdict-token logprobs where the endpoint returns them — if it can't, the fallback and the reason are recorded in config and the PR; tests run against a fake OpenAI-compatible endpoint.

### R5 — Serve the Gemma 4 31B-it judge with vLLM [GPU: H100]
- status: todo
- owner: —
- claimed_at: —
- deps: R4
- source: gateprobe_plan.md § Validation plan, § Budget and compute; memory/reference-dgx-usage.md
- done-when: a compose file under `deploy/vllm-judge/` serves Gemma 4 31B-it with vLLM on d.dgx **GPU #7 only**, every file under `/data/storage/kaluzhnaya_jhub/gate-probe/`, occupancy checked first; the weight fit is recorded — bf16 weights are ~62 GB, more than the ~40 GB share next to `kaluzhnaya_stale_runner`, so either GPU 7 is free or an FP8 checkpoint is used (record which; never stop that container; if neither works, block and ask); the R4 adapter returns verdicts for 10 corpus probes through `d.dgx:<port>`; served model name, revision and dtype recorded in `configs/gates.yaml`; bring-up and teardown commands documented in `deploy/vllm-judge/README.md`.

### W1 — Paper skeleton (IEEEtran, 4 pages, single-anonymous)
- status: done
- note: taken on direct request from jrzkaminski (paper template, one section per file)
- owner: —
- claimed_at: —
- deps: E0.1
- source: gateprobe_plan.md § Submission checklist; Mon DoD "paper skeleton"; docs/icse27-demo-cfp.md; human rule 2026-10-19 (one section per .tex file)
- done-when: the official IEEE `IEEEtran.cls` and `IEEEtran.bst` are vendored unchanged in `paper/`; `paper/main.tex` uses `\documentclass[10pt,conference]{IEEEtran}` with no compsoc option and untouched margins and spacing, and only `\input`s `paper/sections/*.tex` — one section per file; `scripts/check_paper.py` lints all of this in the gate; sections cover what a demo must communicate (envisioned users, the SE challenge, the workflow, validation results plus the planned-study design, related work, the carbon-footprint sentence); author names and affiliations present; `paper/references.bib` seeded with the works in the plan's novelty table and DeepTest — each entry checked to exist (arXiv/DOI) before it is added, and never the unpublished authority or supersession work (human rule, 2026-10-19); `scripts/build_paper.sh` builds with latexmk and fails when the PDF exceeds 4 pages including references.

### H1 — HotCRP accounts and ORCIDs for all four authors [HUMAN]
- status: todo
- owner: —
- claimed_at: —
- deps: —
- source: gateprobe_plan.md § Submission checklist; Mon DoD "HotCRP accounts"; open question 5
- done-when: every author has an icse27demos.hotcrp.com account and an ORCID; recorded in STATUS.md.

---

## Day 1 — Tue 20 Oct: 300 probes, E/M/I/A generators, first full run, floor, report v0, judge overnight

### C4 — Generators: Equivalence (E) and Irrelevance (I)
- status: todo
- owner: —
- claimed_at: —
- deps: C2 C3
- source: gateprobe_plan.md § Metamorphic relations (E, I); Tue DoD
- done-when: `gateprobe/relations/equivalence.py` and `irrelevance.py` implement every E and I transform in `docs/RELATIONS.md` and nothing else; generators are deterministic (seeded, seed stored on each variant) and each variant carries parent id, class, transform and expected outcome; E transforms preserve meaning by construction — flag maps and normalizations come from explicit tables with a unit test per entry; the policy re-rendering transform uses the C3 renderings; `gateprobe expand` writes `variants/*.jsonl` and prints counts per class × transform (also in the PR); a test checks every probe's `policy_id` exists under `policies/`.

### C5 — Generators: Monotonicity (M) and Adversarial (A)
- status: todo
- owner: —
- claimed_at: —
- deps: C2 C3
- source: gateprobe_plan.md § Metamorphic relations (M, A); arXiv 2609.26758; Tue DoD
- done-when: `gateprobe/relations/monotonicity.py` and `adversarial.py` implement every M and A transform in `docs/RELATIONS.md` and nothing else; each M transform strictly raises risk (add `--force`/`-f`, widen scope `./build` → `~` → `/`, drop `--dry-run`, read → write, add `sudo`, pipe a download into `sh`) with a unit test; A covers the injected claims ("user pre-approved this", "test environment", "safe per policy"), text arguing for its own classification, the option-name swap (yes/no → 0/1 → A/B) and the rubric-to-name swap replicating 2609.26758, applied where the adapter mode has named options; deterministic and seeded; counts per transform in the PR; `gateprobe expand` includes them.

### C6 — Corpus to 300 probes
- status: todo
- owner: —
- claimed_at: —
- deps: C2
- source: gateprobe_plan.md Tue DoD; risk "Corpus and labels run late"
- done-when: ≥ 300 probes validate against the schema (the plan's fallback — ship ≥ 200 if fewer than 200 exist on Tuesday night — applies only once a human records it in STATUS.md); no two probes are the same call after normalization; tier × tool-family balance updated in `docs/CORPUS.md`; the corpus rebuilds deterministically from the committed script.

### C7 — Labeled subset: stratified sample and labeling sheet
- status: todo
- owner: —
- claimed_at: —
- deps: C6
- source: gateprobe_plan.md § Tool design (about 60 hand labels, calibration figure only)
- done-when: `scripts/sample_labels.py` draws a seeded, tier-stratified sample of 60 probes; `docs/LABELING.md` gives the labeling instruction (should this call be blocked under its policy? allow / deny) and the edge-case rules; a sheet or small CLI writes `probes/labels.jsonl` with labeler ids; the docs state that labels serve only the calibration figure and are never used to tune generators, prompts or thresholds.

### H2 — Hand-label the 60-probe subset [HUMAN]
- status: todo
- owner: —
- claimed_at: —
- deps: C7
- source: gateprobe_plan.md § Tool design; labels are off the critical path
- done-when: `probes/labels.jsonl` committed with 60 labels and labeler ids; recorded in STATUS.md.

### C8 — Paraphrase class (P): open-model rewrites, labeled as such [GPU: H100 or RTX]
- status: todo
- owner: —
- claimed_at: —
- deps: C2 C3 G1
- source: gateprobe_plan.md § Metamorphic relations (P); memory/decision-llm-routing.md
- done-when: `gateprobe/relations/paraphrase.py` rewrites commands (`rm -rf build` ↔ `find build -delete`) and policies with an open model whose id, revision, prompt and temperature are fixed in config; every output is class P and never mixed into E; the generated set is frozen in `variants/` with its sha256; a hand-checked sample of 20 pairs in the PR says which rewrites are not equivalent (P is the explicitly weaker class).

### R6 — Analysis: floor, flip rates, intervals, calibration, threshold band
- status: todo
- owner: —
- claimed_at: —
- deps: R2 C1
- source: gateprobe_plan.md § Tool design (Analysis); RQ1–RQ3
- done-when: `gateprobe/analysis/` implements exactly the scoring rules pre-registered in `docs/RELATIONS.md`: per-gate test–retest floor from identical repeats; flip rate per relation above the floor with Wilson 95% intervals; mean absolute p_block shift; M risk-inversion share by transform; ECE and reliability bins on the labeled subset; the threshold-band recommendation (the widest band of thresholds no E or I variant crosses); P reported apart from E; each function unit-tested on synthetic runs with hand-computed answers; outputs are distilled CSVs under `results/`.

### R8 — Claude judge backend: Anthropic SDK and the Message Batches API
- status: todo
- owner: —
- claimed_at: —
- deps: R2 R4
- source: human decision 2026-10-19 (Claude judge on Opus 5.5 via the Batch API, ~$200 budget); memory/decision-llm-routing.md
- done-when: written after reading the claude-api skill (Python README and batches guide) — never from memory; the R4 judge adapter gains an `anthropic` backend on the official `anthropic` SDK (an optional `[claude]` extra, imported lazily, so the gate never needs it) using the frozen R4 judge prompt unchanged; model `claude-opus-5-5` and its `effort` level pinned in `configs/gates.yaml` (no temperature or thinking settings — this model rejects sampling parameters and keeps thinking on); verdict and a stated p_block come back through structured output, recorded as a stated probability, not a logprob; `gateprobe run` can submit a run as Message Batches, poll them, write every result into the R2 cache under the same key scheme (repeat index included) and resume a half-collected batch; `stop_reason: refusal` is stored as a refusal outcome and never re-run on another model (that would swap the gate under test); spend from each result's usage at the batch price is appended to `results/spend.csv`; tests use recorded batch fixtures with no network.

### I1 — HTML report v0
- status: todo
- owner: —
- claimed_at: —
- deps: R6
- source: gateprobe_plan.md § Tool design (Outputs); Tue DoD "report v0 renders"
- done-when: `gateprobe report <run>` writes one self-contained HTML file (no network requests when opened) with the flip table per relation × gate with 95% intervals, the reliability diagram, and the top-20 flip examples before/after; every number shows its repeat count; a test renders it from a fixture run and asserts no key-like string can appear in it.

### X1 — First full run: Jev + rule gate, 3 repeats, floor measured [API: OpenRouter]
- status: todo
- owner: —
- claimed_at: —
- deps: G1 C4 C5 R1 R2 R3 R6
- source: gateprobe_plan.md RQ1–RQ3; Tue DoD; risks "Decisions API instability", "Nondeterminism swamps the signal"
- done-when: `docs/experiments/x1-jev-rules.md` is committed and pushed with `status: planned` (decision rules copied from `docs/RELATIONS.md`, $ cap stated) **before** the run; the full corpus × E/M/I/A variants × 3 repeats runs through Jev (mode per G1) and the rule gate under the config $ cap (the plan expects about $0.55–1.10 for Jev); the report then records per gate the floor, flip rates per relation with Wilson intervals, M risk inversions, A shifts, spend and wall-clock, with distilled CSVs in `results/`, each relation classified positive / neutral / negative; a Jev floor above 10% is flagged for the plan's 5-repeat rerun in X4; if the Decisions API stays unreachable, mark blocked — the 12-hour fallback (Clef and the judge only) is a human call.

### X2 — Judge full run: Gemma 4 31B-it, 3 repeats, overnight [GPU: H100]
- status: todo
- owner: —
- claimed_at: —
- deps: G1 C4 C5 R2 R5 R6
- source: gateprobe_plan.md § Budget and compute ("start it Tuesday evening"); RQ1–RQ3
- done-when: same protocol as X1 in `docs/experiments/x2-judge.md` (planned report pushed before launch); launched Tuesday evening so it finishes overnight; served model, revision and dtype recorded; after the run, `docker compose down` and cleanup per memory/reference-dgx-usage.md.

### X7 — Claude judge full run: Opus 5.5 via the Batch API, 3 repeats [API: Anthropic]
- status: todo
- owner: —
- claimed_at: —
- deps: G1 C4 C5 R2 R6 R8
- source: human decision 2026-10-19; RQ1–RQ3; memory/decision-llm-routing.md
- done-when: `docs/experiments/x7-claude-judge.md` is pushed as `planned` before any call (decision rules copied from `docs/RELATIONS.md`; the $ cap, at most $200 minus the Claude spend so far); a ~50-call pilot measures input and output tokens (thinking included) and projects the full run's cost into the report — if the projection exceeds the cap, mark blocked and ask; the full corpus × E/M/I/A variants × 3 repeats then goes to `claude-opus-5-5` as Message Batches with the frozen judge prompt and pinned effort; refusals are counted as their own outcome; the report gives the same outputs as X1 (floor, flip rates with Wilson intervals, M inversions, A shifts, spend, wall-clock), says that p_block is a stated probability, and classifies each relation positive / neutral / negative.

### W2 — Abstract, introduction and related work
- status: todo
- owner: —
- claimed_at: —
- deps: W1
- source: gateprobe_plan.md § Problem and envisioned users, § Novelty and related work
- done-when: a draft abstract (needed for the H3 registration); the introduction states the envisioned users and the SE challenge (a gate is a security component whose specification is the policy; GateProbe is its test suite — metamorphic testing of an ML component applied to a new component class with a natural risk order); the related-work paragraph covers every row of the plan's novelty table and uses the positioning sentence; the unpublished authority and supersession work is neither cited nor mentioned (human rule, 2026-10-19); every factual claim about gate fragility cites a source checked to exist and says what the source says — `paper/references.bib` and the introduction's header comment record where the sources differ from the proposal (e.g. 2609.26758: up to 70.4 pp more flips with yes/no names, AUC 93.8% → 23.2%; the limitations page is Jev 1.13's; the `rm -rf ~/.ssh` 0.76 → 0.48 drop is one integration test); still ≤ 4 pages.

### W3 — Tool design and workflow section
- status: todo
- owner: —
- claimed_at: —
- deps: W1 C1 R2
- source: gateprobe_plan.md § Tool design, § Metamorphic relations
- done-when: the paper describes inputs, relation engine, runner, adapters, analysis and outputs, with the relation-class table; every command shown matches the real CLI `--help`; no figure beyond the three the plan budgets (flip table, reliability diagram, case-study box); still ≤ 4 pages.

---

## Day 2 — Wed 21 Oct: second decision model, hook end to end, Docker builds, go/no-go at 18:00

### X3 — Second decision model(s) [API: OpenRouter]
- status: todo
- owner: —
- claimed_at: —
- deps: X1
- source: gateprobe_plan.md § Validation plan; open question 3; § Budget and compute
- done-when: the model(s) G1 chose (Cloudflare Clef and/or Mercury Decide; GPT-6 Luna Decisions only if its pricing, checked and recorded first, keeps the run under a $20 cap) are pinned in `configs/gates.yaml`; `docs/experiments/x3-second-decision-model.md` is pushed as `planned` before the run; same protocol and outputs as X1.

### I2 — Claude Code PreToolUse hook (live demo)
- status: todo
- owner: —
- claimed_at: —
- deps: R1 R2
- source: gateprobe_plan.md § Tool design (Live hook); Wed DoD "hook demo works end to end"
- done-when: `integrations/claude-code/` has a `PreToolUse` hook and a settings snippet that send the real tool call to the configured gate, print the verdict and p_block, and warn when a relation known to be fragile for that gate applies (read from a run's results); the hook can run from the cache (replay) so the demo never depends on the live API; tested end to end in a scratch project with recorded responses; it never prints or logs a key; install steps in the README.

### I3 — CI mode and GitHub Action
- status: todo
- owner: —
- claimed_at: —
- deps: R6
- source: gateprobe_plan.md § Tool design (Outputs)
- done-when: `gateprobe ci --max-flip 0.05` exits non-zero when any relation's flip rate above the floor exceeds the threshold (the rule is spelled out in `--help` and the README); an `action.yml` composite action wraps it; tests cover the pass and fail exit codes on fixture runs.

### I4 — Docker image
- status: todo
- owner: —
- claimed_at: —
- deps: R2
- source: gateprobe_plan.md § Tool design (Packaging); Wed DoD "Docker builds"
- done-when: the `Dockerfile` builds locally; `docker run … gateprobe replay` reproduces a fixture run's report with no API key and no network; image size and the build command in the README; publishing the image is H5, not this step.

### G2 — Decision point 2: go/no-go on scope (Wed 21, 18:00) [GATE]
- status: todo
- owner: —
- claimed_at: —
- deps: X1
- source: gateprobe_plan.md § Risks and decision points (2)
- done-when: the loop writes `docs/gates/g2-go-no-go.md` — the state of every step, the X1/X2/X3 numbers that exist, spend so far, the risk-table triggers that fired, and the plan's three options (full: two or three decision models + judge + rules; reduced: Jev + judge + rules; pivot the engine to ToolSense) with a recommendation — then `mark.py G2 blocked "awaiting human decision"`. The humans record the decision in STATUS.md, mark `cut` whatever leaves scope (the `[STRETCH]` steps on reduced or pivot), and run `mark.py G2 done`. A pivot rewrites this ledger — that is a human plan change.

### X6 — Sandbox validation of P pairs [STRETCH]
- status: todo
- owner: —
- claimed_at: —
- deps: G2 C8
- source: gateprobe_plan.md § Metamorphic relations ("Stretch, after the Wednesday gate")
- done-when: only with G2 = full scope: both commands of each P pair run in a throwaway sandbox (container, no network) and the filesystems are diffed; only pairs with identical effects count as equivalent; `docs/experiments/x6-p-sandbox.md` reports how many P pairs survive and how the P flip rates change.

### I7 — OpenCode permission plugin [STRETCH]
- status: todo
- owner: —
- claimed_at: —
- deps: G2 I2
- source: gateprobe_plan.md § Tool design (Live hook, "if time allows"); open question 4
- done-when: only with G2 = full scope and G1's answer to open question 4 including OpenCode: an OpenCode permission plugin with the same behavior and tests as the I2 hook.

---

## Day 3 — Thu 22 Oct: results frozen at 12:00, three figures, full draft, storyboard, Docker on a clean machine, hook segment

### X4 — Final runs: P class, 5-repeat reruns, RQ4 cost, consolidated results [API: OpenRouter] [API: Anthropic] [GPU: H100]
- status: todo
- owner: —
- claimed_at: —
- deps: X1 X2 X3 X7 C8
- source: gateprobe_plan.md RQ1–RQ4; risk "Nondeterminism swamps the signal" (floor above 10% → 5 repeats)
- done-when: `docs/experiments/x4-final-results.md` pushed as `planned` first; the P variants run on every in-scope gate; any gate whose floor exceeded 10% is rerun with 5 repeats; RQ4 gives dollars and wall-clock per 1,000 probes per gate from the logged spend and timings; consolidated CSVs in `results/` and the report give RQ1–RQ4 per gate with every number's repeat count and 95% interval; ready for the 12:00 freeze.

### G3 — Decision point 3: results frozen (Thu 22, 12:00) [GATE]
- status: todo
- owner: —
- claimed_at: —
- deps: X4
- source: gateprobe_plan.md § Risks and decision points (3)
- done-when: the loop writes `docs/gates/g3-results-freeze.md` — every number the paper and the video will use, with the commit hash that freezes `results/` — then `mark.py G3 blocked "awaiting human decision"`. The humans confirm in STATUS.md and run `mark.py G3 done`. From then on `results/` gets no new rows and only W-lane steps (plus packaging fixes that change no number) land.

### X5 — Case studies (paper box and video)
- status: todo
- owner: —
- claimed_at: —
- deps: X4
- source: gateprobe_plan.md § Validation plan (case studies)
- done-when: from the frozen runs only, `docs/experiments/x5-case-studies.md` gives (1) a destructive command auto-approved after an E or P rewrite and (2) the "pre-approved" injection moving Jev's p_block across the configured threshold, each reproduced from the cache with exact before/after inputs and probabilities; if either case does not occur in the data, the report says so — no searching outside the frozen runs.

### R7 — The three figures, final
- status: todo
- owner: —
- claimed_at: —
- deps: X4 X5 H2
- source: gateprobe_plan.md § Validation plan (three figures); Thu DoD
- done-when: committed scripts regenerate, in one command and from `results/` only, (1) the flip-rate table relation × gate with 95% intervals, (2) the reliability diagram (Jev against the judge on the labeled subset) and (3) the before/after case-study box from X5; vector output sized for IEEEtran columns; no hand-edited numbers.

### W4 — Validation section and planned study
- status: todo
- owner: —
- claimed_at: —
- deps: G3 R7
- source: gateprobe_plan.md § Validation plan; § Submission checklist
- done-when: RQ1–RQ4 reported from the frozen numbers only (each with repeats and interval, matching `docs/gates/g3-results-freeze.md`); the three figures; both case studies; the planned 8–10-developer study described, not run; the carbon-footprint sentence; negative results stated plainly (if E flips sit at the floor, the section leads with M and A, as the plan's risk table says); still ≤ 4 pages.

### W5 — Full paper draft, 4-page check
- status: todo
- owner: —
- claimed_at: —
- deps: W2 W3 W4
- source: gateprobe_plan.md Thu DoD "full paper draft"
- done-when: the complete draft builds with `scripts/build_paper.sh` at ≤ 4 pages including references; the PR description ticks each submission-checklist item the PDF itself satisfies and lists the rest with their owner.

### W6 — Video storyboard, voice-over script, captions
- status: todo
- owner: —
- claimed_at: —
- deps: W1
- source: gateprobe_plan.md Thu DoD "storyboard written"; § Submission checklist (video)
- done-when: `video/storyboard.md` plans 3–5 minutes that show the tool running (CLI run, report, CI mode, the live hook segment), not slides; `video/voiceover.md` and `video/captions.srt` timed to the script; a pre-recording checklist (no keys or `.env` on screen, clean terminal history, the hook against the cached gate); the case-study shots use X5 once it lands.

### I5 — Replay bundle, hosted report page, clean-machine check
- status: todo
- owner: —
- claimed_at: —
- deps: I1 I4 G3
- source: gateprobe_plan.md § Tool design (Packaging); Thu DoD "Docker verified on a clean machine"
- done-when: one command builds the replay bundle (frozen `cache/` + run JSONL + sha256 manifest); the report for the frozen runs is generated as a static page ready for GitHub Pages; on a clean machine or a fresh container, the README's reviewer path — pull the image, fetch the bundle, `gateprobe replay`, `gateprobe report` — works with no key and nothing to build; publishing is H5.

### I6 — Public release branch (reproduction-only, identity-clean)
- status: todo
- owner: —
- claimed_at: —
- deps: I5
- source: gateprobe_plan.md § Submission checklist (public repo); latent-underspecification-research A4.6 precedent
- done-when: an orphan `release` branch (or an export for a separate public repo — the humans choose at H5) holds code, configs, probes, policies, variants, results, tests, the Dockerfile, the action and a reviewer README, without the agent pipeline (`.claude/`, `docs/PLAN.md`, `docs/AUTONOMY.md`, `memory/`, `STATUS.md`, `gateprobe_plan.md`); a scan finds no `.env`, keys, internal hostnames (d.dgx, a.dgx, b.dgx, gpubox, NSSLabPC), storage paths, private IPs, or mention of the unpublished authority or supersession work (the policy provenance note in `policies/README.md` included — the humans decide what it says publicly); nothing is pushed public by this step.

### H3 — Register the submission on HotCRP (by Thu 22) [HUMAN]
- status: todo
- owner: —
- claimed_at: —
- deps: H1 W2
- source: gateprobe_plan.md § Submission checklist (registration by Thursday 22 Oct)
- done-when: the submission is registered at icse27demos.hotcrp.com with title, the W2 abstract, all authors and ORCIDs; recorded in STATUS.md.

### H4 — Record the hook segment [HUMAN]
- status: todo
- owner: —
- claimed_at: —
- deps: I2 W6
- source: gateprobe_plan.md Thu DoD "hook segment recorded"; risk "Hook demo flaky on camera"
- done-when: the live-hook segment is recorded on Thursday against the cached gate, or the humans fall back to a CLI-only video (the plan's fallback); recorded in STATUS.md.

---

## Day 4 — Fri 23 Oct: video uploaded, URL in the abstract, 4-page check, submitted in the evening

### H5 — Publish: public repo, Docker image, hosted report, replay bundle [HUMAN]
- status: todo
- owner: —
- claimed_at: —
- deps: I6
- source: gateprobe_plan.md § Submission checklist (reviewers must not have to build code)
- done-when: the humans pick the namespaces and publish the public repo from the I6 release, the image (Docker Hub or GHCR), the report page and a GitHub Release carrying the replay bundle; links recorded in STATUS.md and the public README.

### H6 — Record, edit and upload the video [HUMAN]
- status: todo
- owner: —
- claimed_at: —
- deps: W6 H4
- source: gateprobe_plan.md Fri DoD; § Submission checklist (video)
- done-when: 3–5 minutes with voice-over and captions, the tool running rather than slides, no keys on screen; uploaded to YouTube (unlisted is fine); URL recorded in STATUS.md.

### W7 — Submission PDF
- status: todo
- owner: —
- claimed_at: —
- deps: W5 H5 H6
- source: gateprobe_plan.md § Submission checklist; Fri DoD
- done-when: the video URL is appended to the end of the abstract; the H5 links are in the paper; model versions pinned and repeats/intervals present for every number; `bash scripts/build_paper.sh --final` passes (lint, no `\todo` left, ≤ 4 pages); every submission-checklist item is ticked or assigned in the PR; the final PDF is built.

### H7 — Submit on HotCRP (Fri 23 evening; hard stop Sat 24 13:59 CEST) [HUMAN]
- status: todo
- owner: —
- claimed_at: —
- deps: W7 H3
- source: gateprobe_plan.md § Submission checklist
- done-when: the W7 PDF and the abstract with the video URL are submitted on HotCRP; confirmation recorded in STATUS.md.
