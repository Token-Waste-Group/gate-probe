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

## Docker

```bash
docker build --build-arg GIT_HASH=$(git rev-parse HEAD) -t gateprobe .   # ~270 MB
# replay recorded runs and render the report: no API key, no network
docker run --rm --network none -v "$PWD/cache:/gateprobe/cache:ro" -v "$PWD/runs:/gateprobe/runs" \
  gateprobe replay --gate jev --variants variants/generated.jsonl --run-id replay
docker run --rm --network none -v "$PWD/runs:/gateprobe/runs:ro" -v "$PWD/reports:/gateprobe/reports" \
  gateprobe report --runs runs/replay.jsonl --out reports/replay.html
```

The image holds the CLI, configs, policies, probes and variants, and never
`.env`, the cache or local state (`.dockerignore`). The replay bundle (I5)
supplies `cache/`. Publishing the image is a human step (H5).

## Reviewer path: replay the frozen results (no key, no network)

The replay bundle holds the cache entries behind every number in the paper:
94,589 entries for the 12 frozen runs, 115,020 rows over six gates. It also
holds the run files and a sha256 manifest. Nothing needs building: pull the
image and fetch the bundle. Publishing both is H5; until then, `docker build`
the image as above.

```bash
IMAGE=gateprobe                                   # the published image once H5 is done
tar xzf gateprobe-replay-19fd14a.tar.gz && cd gateprobe-replay-19fd14a
shasum -a 256 -c MANIFEST.sha256 --quiet          # (sha256sum on Linux) every file intact
# replay a gate from the cache: seconds; --allow-misses records the one call drex's frozen
# run never got an answer for (an HTTP 520) as replay_miss instead of stopping
docker run --rm --network none -v "$PWD/cache:/gateprobe/cache:ro" -v "$PWD/runs:/gateprobe/runs" \
  $IMAGE replay --gate drex --variants variants/generated.jsonl --run-id replay-drex --allow-misses
# the report over the frozen runs: the hosted page
mkdir -p reports
docker run --rm --network none -v "$PWD/runs:/gateprobe/runs:ro" -v "$PWD/reports:/gateprobe/reports" \
  $IMAGE report --runs runs/x[0-9]*.jsonl --variants variants/generated.jsonl variants/paraphrase.jsonl \
  --out reports/frozen.html
```

The gates are `jev`, `rules`, `judge-claude`, `gpt-6-luna-decisions`,
`pplx-decider` and `drex`. P variants replay the same way with
`--variants variants/paraphrase.jsonl`.

To build the bundle and the page (`dist/`) from a working copy with the
cache, run `uv run python scripts/build_bundle.py`. To check a replay against
the frozen rows, run `uv run python scripts/compare_runs.py --frozen … --replayed …`.
