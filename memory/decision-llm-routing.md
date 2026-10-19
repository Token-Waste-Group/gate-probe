# Decision: model routing and budget for GateProbe

**Type:** decision (derived 2026-10-19 from `gateprobe_plan.md` § Validation
plan and § Budget and compute, plus the human's routing rule restated in
[[reference-dgx-usage]]; the humans may amend it). **Audience:** every agent
implementing an adapter, a run, or the paraphrase generator.

**Gates under test go through the adapter the plan names — that route is part
of what is being tested:**

1. **Decision models → the OpenRouter Decisions API** (`decisions` adapter,
   `OPENROUTER_API_KEY`): Jev 1.14 pinned as `typesafe/jev-1.14`, plus the
   second model(s) chosen at G1 (Cloudflare Clef, Mercury Decide). Clef has open
   weights, but it is still tested through the Decisions API. GPT-6 Luna
   Decisions only after its pricing is checked and recorded, under a $20 cap.
2. **The LLM judge → vLLM on the H100** (`judge` adapter, Gemma 4 31B-it on
   d.dgx GPU #7 per [[reference-dgx-usage]]). Other judges, if a human adds
   one, may go through OpenRouter's chat endpoint.
3. **Rule gate → local**, no model.

4. **Claude → the Anthropic API** (`ANTHROPIC_API_KEY` in `.env`; **about $200
   for the project**, human 2026-10-19; separate from the < $20 OpenRouter
   budget). The human offered it for the experiments, e.g. as a judge. A Claude
   judge **gate** is not among the plan's four, so adding one needs a
   human-confirmed plan step first (proposed 2026-10-19). Notes for whoever
   builds it (as of 2026-10-19, from the claude-api skill — re-check before a
   run): use the official `anthropic` SDK, not an OpenAI-compatible shim; the
   default model is `claude-opus-5-5` unless the humans pick another (prices
   per MTok in/out: Opus 5.5 $4/$20, Sonnet 5.5 $2/$10, Haiku 5.5 $0.10/$0.50;
   the Batch API halves them); no logprobs are documented, so p_block is a
   stated probability via structured output — record it as such, it is weaker
   than a logprob-based one for the floor and ECE; Opus 5.5 can't disable
   thinking and rejects sampling parameters, so pin `effort` (e.g. `low`) in
   config instead of temperature, and measure output tokens on a ~50-call pilot
   before the full run.

**Auxiliary model work (not a gate under test) follows the human's order:**
Claude via `ANTHROPIC_API_KEY` first, open models on the H100 (or the RTX boxes
when small enough) next, OpenRouter only for open models that don't fit. The P
paraphrase generator uses an open model on the H100/RTX, fixed in config.

**Not covered:** any other proprietary model. If a step seems to need one,
stop and ask the human; don't route it on your own.

**Rules for every model-calling path:**
- Provider, pinned model id, prompt and temperature (0) — or `effort` where a
  model rejects sampling parameters, as current Claude models do — are fixed
  in config.
- A $ cap per run is read from config; spend is appended to
  `results/spend.csv` (gate, model, tokens, USD, run id) and summed in the
  step's report. OpenRouter spend stays under $20 (the plan estimates ~$0.55
  per decision model per 3-repeat run). Before any Claude run, check that
  cumulative Claude spend plus the run's cap stays under $200.
- Never substitute a different model silently — if the pinned one can't be
  reached, block and ask (the 12-hour Jev fallback is a human call).

**How to apply:** read this before R1, R4, R5, C8 and every X step, together
with [[decision-research-discipline]].
