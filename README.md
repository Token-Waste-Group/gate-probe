# GateProbe

A metamorphic testing harness for the permission gates that approve or deny
coding-agent tool calls. It is the artifact of the ICSE 2027 Tool Demonstration
and Data Showcase paper *GateProbe*.

- Paper: [`paper/gateprobe.pdf`](paper/gateprobe.pdf)
- Demo: <https://huggingface.co/spaces/TokenWasteGroup/gateprobe>
- Video: <https://youtu.be/rZ6yazAzKs8>
- Replay bundle: [`gateprobe-replay-ee08ca1.tar.gz`](https://github.com/Token-Waste-Group/gateprobe/releases/download/v1.0/gateprobe-replay-ee08ca1.tar.gz) (release [v1.0](https://github.com/Token-Waste-Group/gateprobe/releases/tag/v1.0))
- Development history: the [`dev`](https://github.com/Token-Waste-Group/gateprobe/tree/dev) branch

A gate takes a policy, a tool call and context, and returns allow or deny with a
probability. It can be a typed decision model on the OpenRouter Decisions API,
an LLM judge, or a rule set. GateProbe rewrites those inputs under relations
whose expected outcome is known:
- an equivalent rewrite must not change the verdict (E);
- a strictly riskier call must not get a looser one (M);
- irrelevant or injected text must not move it (I, A);
- a model paraphrase is reported apart, as the weaker class P.

It reports violations per relation and per gate, with each gate's test–retest
noise floor subtracted. No ground truth is needed.

## What is here

| Path | What |
|---|---|
| `src/gateprobe/` | the CLI: corpus, relation generators, gate adapters, runner with cache and replay, analysis, HTML report, CI check, Claude Code hook |
| `probes/corpus.jsonl` | 300 tool calls (shell, git, filesystem, package managers, network) in four risk tiers, under four policies; datasheet in `docs/CORPUS.md` |
| `policies/` | the four policies, each in YAML, JSON, prose and bullets, plus the rule gate's rule sets |
| `variants/` | the frozen variants: `generated.jsonl` (300 base items, 1,621 E, 436 M, 1,452 I, 2,052 A; seeded) and `paraphrase.jsonl` (529 P) |
| `docs/RELATIONS.md` | the relation spec and the scoring rules, pre-registered before any run |
| `docs/experiments/` | the run reports, as written during the study, including negative results |
| `results/` | the distilled results; `results/x2-seven-gates/` holds the paper's tables |
| `configs/` | the pinned gate models, run settings and the judge prompt |
| `integrations/` | the Claude Code `PreToolUse` hook and the Hugging Face Space replay demo |
| `tests/` | the test suite; it never touches the network |

## Install

```bash
pip install -e ".[dev]"          # Python >= 3.11; add ,claude for the Claude judge
pytest -q                        # the suite runs offline
```

Or use the Docker image (no key, no network needed for replay):

```bash
docker build --build-arg GIT_HASH=<commit> -t gateprobe .
```

## Replay the frozen results (no key, no network)

The replay bundle `gateprobe-replay-ee08ca1.tar.gz` holds the 113,654 recorded
gate answers behind every number in the paper: 14 runs, 134,190 rows over seven
gates, R = 3 repeats. It also holds the run files and a sha256 manifest.

```bash
tar xzf gateprobe-replay-ee08ca1.tar.gz && cd gateprobe-replay-ee08ca1
shasum -a 256 -c MANIFEST.sha256 --quiet          # (sha256sum on Linux)
# replay a gate from the cache; --allow-misses records the one call drex's frozen run never
# got an answer for (an HTTP 520) as replay_miss instead of stopping
docker run --rm --network none -v "$PWD/cache:/gateprobe/cache:ro" -v "$PWD/runs:/gateprobe/runs" \
  gateprobe replay --gate drex --variants variants/generated.jsonl --run-id replay-drex --allow-misses
# the HTML report over the frozen runs
mkdir -p reports
docker run --rm --network none -v "$PWD/runs:/gateprobe/runs:ro" -v "$PWD/reports:/gateprobe/reports" \
  gateprobe report --runs runs/x[0-9]*.jsonl --variants variants/generated.jsonl variants/paraphrase.jsonl \
  --out reports/frozen.html
```

The gates are `jev`, `rules`, `judge-claude`, `judge-gemma`,
`gpt-6-luna-decisions`, `pplx-decider` and `drex`. With colima on macOS, unpack the bundle under your
home directory: colima shares only `~` with its VM.

`python scripts/compare_runs.py --frozen runs/x3-drex.jsonl --replayed runs/replay-drex.jsonl`
checks a replay against the frozen rows. To re-score the frozen runs, use
`gateprobe analyze --runs <the 14 runs> --name check --variants variants/generated.jsonl variants/paraphrase.jsonl`.
Run it from this tree with the bundle's `runs/` copied in, so `results/spend.csv`
is found. It writes `results/check/`, which matches `results/x2-seven-gates/`.

## Run your own gate

```bash
gateprobe expand                                   # variants/generated.jsonl from the corpus
gateprobe run --gate jev --variants variants/generated.jsonl --workers 8   # needs OPENROUTER_API_KEY in .env
gateprobe analyze --runs runs/<run-id>.jsonl --name my-run
gateprobe report --runs runs/<run-id>.jsonl --out reports/my-run.html
gateprobe ci --runs runs/<run-id>.jsonl --max-flip 0.05     # non-zero exit when a relation fails
```

Keys are read from `.env`: `OPENROUTER_API_KEY` for the Decisions API gates and
`ANTHROPIC_API_KEY` for the Claude judge. The Gemma judge needs no key: it
expects a vLLM server at `localhost:8017`, and `configs/gates.yaml` pins its
model, revision, dtype, server image and flags. Every run has a dollar cap
(`configs/run.yaml`) and logs its spend to `results/spend.csv`. A new gate is
an entry in `configs/gates.yaml`. The adapters are `decisions`, `judge`
(OpenAI-compatible or Anthropic) and `rules`.

`gateprobe ci` fails when a relation's flip rate above the floor is
significantly positive and exceeds `--max-flip`. `action.yml` wraps it as a
GitHub Action. The live hook is in `integrations/claude-code/`.

## Differences from the development tree

This tree is the development repository without its planning records. One
comment in `configs/gates.yaml` named an internal host and was removed, so the
file's sha256 differs from the frozen input listed in the bundle's
`BUNDLE.json`. The parsed configuration, and so every run's `config_hash`, is
identical.
