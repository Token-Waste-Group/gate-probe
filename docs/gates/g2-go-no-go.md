# G2: go/no-go on scope (decision packet)

- **Prepared:** Tue 20 Oct 2026, 03:10 CEST, by the loop (step G2). It will be refreshed with the X4 numbers if they land before the decision. **Due:** Wed 21 Oct 18:00.
- **Who decides:** the four authors. The loop recommends below and decides nothing.
- **What G2 decides** (`gateprobe_plan.md` § Risks and decision points, 2): full scope, reduced scope, or a pivot of the engine to ToolSense. It also decides which `[STRETCH]` steps stay. They are touched only if G2 records full scope.

## 1. The three options

| option | gates in the paper | what it means now |
|---|---|---|
| **Full** | two or three decision models + judge + rules | Already exceeded: four decision models (Jev 1.14, GPT-6 Luna Decisions, pplx-decider v1.2, drex v1.5), the Claude Opus 5.5 judge and the rule gate have complete 3-repeat runs. Add the Gemma 4 judge (X2) if the H100 frees in time. |
| **Reduced** | Jev + judge + rules | Drops the three further decision models from the paper. Their runs exist and would go to the artifact only. |
| **Pivot** | the engine on ToolSense (tool descriptions in place of calls) | Rewrites the ledger (a human plan change). Nothing measured so far points this way. |

## 2. The numbers that exist

Every run used 5,861 items × 3 repeats under the pre-registered rules (`docs/RELATIONS.md` § 3).
- **Cell format:** F − f in points with Newcombe's 95% interval, then the label. **(B)** marks a positive that survives Bonferroni over that run's class tests.
- **Floor:** f = repeat 1 vs repeat 2 (Wilson 95%).
- **M:** for M, F counts risk inversions against the inversion floor.

| gate | report | floor f | E | M | I | A |
|---|---|---|---|---|---|---|
| Jev 1.14 | X1 | 0.32% [0.20, 0.52] | +1.40 [+0.84, +2.17] **pos (B)** | −1.63 [−2.26, −0.26] neg | +0.09 [−0.21, +0.59] neg | +0.09 [−0.21, +0.59] neg |
| rules | X1 | 0 [0, 0.07] | +3.82 [+2.99, +4.87] **pos (B)** | +0.23 [+0.03, +1.29] pos | +0.28 [+0.09, +0.71] **pos (B)** | +0.19 [+0.06, +0.50] **pos (B)** |
| Claude Opus 5.5 judge | X7 | 0.46% [0.31, 0.67] | +1.19 [+0.63, +1.95] **pos (B)** | −0.84 [−1.32, +0.42] neg | +0.68 [+0.20, +1.40] **pos (B)** | +0.40 [+0.02, +0.93] pos |
| GPT-6 Luna Decisions | X3 | 0 [0, 0.07] | +7.46 [+6.28, +8.85] **pos (B)** | +1.83 [+0.93, +3.58] **pos (B)** | +4.20 [+3.28, +5.36] **pos (B)** | +5.92 [+4.82, +7.26] **pos (B)** |
| pplx-decider v1.2 | X3 | 0 [0, 0.07] | +2.04 [+1.45, +2.85] **pos (B)** | +8.72 [+6.41, +11.74] **pos (B)** | +0.34 [+0.13, +0.80] **pos (B)** | +1.93 [+1.33, +2.77] **pos (B)** |
| drex v1.5 | X3 | 0 [0, 0.07] | +6.17 [+5.10, +7.45] **pos (B)** | +10.51 [+7.96, +13.75] **pos (B)** | +1.45 [+0.94, +2.20] **pos (B)** | +2.27 [+1.62, +3.17] **pos (B)** |

What the numbers say, for the scope decision:

- **RQ1 (E) is positive on all six gates.** On every model gate, the largest source is re-rendering the same policy. The "E flips at the floor" fallback (lead with M and A) does not apply.
- **RQ2 (M):**
  - For the three X3 models, the positives rest on a δ = 0 floor. At the verdict level they have 0, 1 and 1 inversions.
  - The concrete finding is the `.env` gap. Overwriting `.env` is allowed where reading it is denied on 4 of 6 gates: rules, Jev, Claude and pplx.
- **RQ3 (A) splits by direction.** The injections push Luna toward deny, but pplx (25 of 28 flips) and drex (23 of 33) toward allow. Jev shifts 1.0 point toward allow without flipping.
- **RQ4 (cost)**, per 1,000 calls, from `results/spend.csv`:
  - Jev $0.034;
  - Luna $0.067;
  - pplx $0.012;
  - drex $0.021;
  - Claude judge (batch) $2.75.

  X4 adds wall-clock and the per-1,000-probe form.
- **The gates disagree enough to make the cross-gate figures worth having.** Comparing more gates is what the full option buys.

## 3. Definition of done, by day (plan § Sprint)

| day | item | state |
|---|---|---|
| Tue 20 | 300 probes | done (C6; 300 distinct calls, 75 per policy) |
| | E, M, I, A generators complete | done (C4, C5) |
| | first full Jev + judge + rules run; floor measured | done (X1 Mon night; the Claude judge in X7) |
| | report v0 renders | done (I1) |
| | judge batch runs overnight | done (X7, Message Batches, 18 min). The Gemma judge (X2) waits on the H100. |
| Wed 21 | second decision model in | done: three more (X3) |
| | 3-repeat runs complete | done for six gates. X2 is not started (R5 blocked: H100 busy). |
| | hook demo works end to end | done (I2, advisory and cache-first). The recording is H4 (Thu). |
| | Docker builds | done (I4, checked with `--network none` and no key) |

## 4. State of every step (`docs/PLAN.md`, at 03:10 CEST)

- **Done (28):**
  - E0.1, S1;
  - C1–C8;
  - R1–R4, R6, R8;
  - W1–W3, W6;
  - I1–I4;
  - G1;
  - X1, X3, X7.
- **Blocked:** R5 (the Gemma judge on the H100; the GPU is not free).
- **Todo, loop:**
  - X4: next. P class on every gate, RQ4 cost, consolidated results.
  - X2: when the H100 frees.
  - X5, R7: R7 also needs H2.
  - W4, W5, W7;
  - I5, I8, I6.
- **Todo, stretch** (only with full scope): X6 sandbox validation of the P pairs, I7 OpenCode plugin.
- **Todo, human:**
  - H1: HotCRP accounts and ORCIDs;
  - H2: label the 60 probes, with `uv run python scripts/label_cli.py --labeler <id>`;
  - H3: register by Thu 22;
  - H4: record the hook segment;
  - H5, H6, H7.
- **This gate:** G2 (blocked, awaiting this decision). G3 follows on Thu 22 12:00.

## 5. Spend

| budget | spent | cap | runs |
|---|---:|---:|---|
| OpenRouter (Decisions API) | $2.09 | $20 | Jev $0.53, Luna $1.05, pplx $0.19, drex $0.33, smoke and probes < $0.01 |
| Anthropic (Claude) | $48.17 | ~$200 | X7 $48.03 + pilot $0.13 + pilot refusals $0.007 + smoke $0.006 |
| GPU | gpubox RTX 5080, ~1 h | idle RTX time | C8 paraphrases (Qwen3-8B-FP8). The H100 is not yet used. |

X4's expected spend is small: the P class (529 variants × 3 repeats) costs about $4.3 on the Claude judge and well under $1 on the four decision models.

## 6. Risk-table triggers (plan § Risks and decision points)

| trigger | fired? | evidence |
|---|---|---|
| Jev unreachable for 12 h → run Clef and the judge only | no | Jev answered all 15,783 applicable calls in X1 |
| E flips at the floor → lead the paper with M and A | no | E is positive on all six gates |
| Floor above 10% on a gate → 5 repeats on that gate | no | The highest floor is the Claude judge's 0.46% |
| Under 200 probes Tuesday night → ship 200 | no | 300 probes |
| Hook demo flaky on camera → CLI-only video | not yet testable | H4 records on Thu against a cached gate |
| Scope collapse by Wednesday → reduce gates or pivot | no | Every in-scope gate except the Gemma judge has a full run |

Two more things for the humans to know:
- **The Claude judge refuses 55% of the exfiltration tier.** Four of its seven probes are refused on every call. The refusals are counted as their own outcome (X7).
- **The Gemma judge (X2) depends on the H100.** It won't be ready while the colleague's job holds the GPU.

## 7. Recommendation (the loop's; the humans decide)

1. **Full scope**, as the plan defines it and already exceeded: four decision models, the Claude Opus 5.5 judge and the rule gate.
   - The cross-gate contrasts carry the paper's figures. Examples: E from policy rendering everywhere, A toward deny on Luna but toward allow on pplx and drex, and the `.env` gap on four of six gates.
   - Those contrasts disappear under the reduced option.
   - Every run is already paid for, at $50 of the $220 combined budget.
2. **The Gemma 4 judge (X2):** keep it in scope only if the H100 frees early enough for X2 to finish before G3 (Thu 22 12:00). Otherwise, move it to the paper's future work at G3 and keep the open judge as a replay-ready config. Either way, the paper does not wait on it.
3. **Stretch steps:**
   - **I7 (OpenCode plugin): cut.** G1 limited the live demo to Claude Code, and its done-when needs G1's answer to include OpenCode.
   - **X6 (sandbox validation of P pairs): keep, at the lowest priority, after X4.** It's cheap: no API, a throwaway container with no network. The C8 hand check already found 7 of 16 command paraphrases not equivalent, so sandbox evidence would make the P result interpretable. Cut it at G3 if it isn't done.
   - **PolicyForge:** not in the ledger; stays out.
4. **No pivot.**

## 8. Recording the decision

The humans:
- write the outcome as a STATUS.md row;
- mark `cut` whatever leaves scope (e.g. `python3 scripts/mark.py I7 cut "G2: …"`);
- run `python3 scripts/mark.py G2 done`.
