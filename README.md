# GateProbe

A metamorphic testing harness for the permission gates that approve or deny
coding-agent tool calls — **ICSE 2027 Tool Demonstration and Data Showcase
track**, submission Fri 23 Oct 2026.

A gate (a typed decision model such as Jev 1.14 via the OpenRouter Decisions
API, an LLM-judge prompt, or a rule set) takes a policy, a tool call and
context, and returns allow or deny with a probability. GateProbe rewrites those
inputs under relations with known expected outcomes — an equivalent rewrite
must not change the verdict, a strictly more dangerous rewrite must not lower
the block probability, irrelevant or injected text must not move it — and
reports violations per relation and per gate, with test–retest noise
subtracted. No ground truth needed. Full proposal:
[`gateprobe_plan.md`](gateprobe_plan.md).

## The autonomous loop

This repo advances itself: `docs/PLAN.md` is the step ledger, `/continue` (in
Claude Code) claims and executes exactly one step to a merged PR, and one agent
per workstream works in parallel race-safely (`/continue C` stays in the corpus
lane). Protocol: [`docs/AUTONOMY.md`](docs/AUTONOMY.md). Working agreement:
[`CLAUDE.md`](CLAUDE.md). Daily log + decision points: [`STATUS.md`](STATUS.md).

```bash
bash scripts/bootstrap.sh     # uv + venv + deps
cp .env.example .env          # set OPENROUTER_API_KEY for Decisions API runs
bash scripts/check.sh         # the gate: ruff + format + pytest
claude                        # then: /continue [lane]  (or «продолжи»)
python3 scripts/claim.py --dry-run   # what's next, and which [HUMAN] steps wait on you
```

## Layout

| Path | What |
|---|---|
| `gateprobe_plan.md` | frozen proposal (tool design, relations, validation, schedule, risks) |
| `docs/PLAN.md` | step ledger / claim board driving the loop |
| `docs/RELATIONS.md` | relation spec + pre-registered scoring rules (C1) |
| `docs/experiments/`, `docs/gates/` | run reports (negatives included); decision packets |
| `configs/` | pinned gate models, run settings, judge prompt — every run is config-driven |
| `probes/`, `policies/`, `variants/` | the corpus, its policies in four renderings, generated variants |
| `src/gateprobe/` | corpus, relations, gates, runner, analysis, report, hook |
| `cache/`, `runs/` | response cache (= replay bundle) and run JSONL — git-ignored |
| `results/` | distilled CSVs, append-only, committed |
| `paper/`, `video/` | IEEEtran paper (4 pages); storyboard, voice-over, captions |

## CI mode

```bash
gateprobe ci --runs runs/*.jsonl --max-flip 0.05 [--classes E,I,A]
```

The check **fails** when, for some gate and relation class, the flip rate
above the test–retest floor (risk inversions above the inversion floor, for M)
is significantly positive (the lower bound of its 95% Newcombe interval is
above 0) **and** its estimate exceeds `--max-flip`. Noise alone can't fail it.
Exit codes: 0 pass, 1 fail, 2 no scorable data. As a GitHub Action, on recorded
run files and so with no API key:

```yaml
- uses: Token-Waste-Group/gate-probe@main
  with:
    runs: runs/x1-jev.jsonl
    max-flip: "0.05"
```
