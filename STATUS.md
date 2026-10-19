# STATUS — one line per day + every decision-point outcome

Convention: updated every evening; decision points (G1 Mon 19 18:00, G2 Wed 21
18:00, G3 Thu 22 12:00) and fallback triggers are recorded here the day they
happen, never silently. Newest first. Day 0 = Mon 19 Oct 2026. Submit Fri 23
Oct evening; hard stop Sat 24 Oct 13:59 CEST / 14:59 MSK (AoE).

| Day | Date | Log |
|-----|------------|-----|
| 0d | 2026-10-19 | **G1 decided (human).** The spec is frozen as written, with all 8 choices confirmed. Further decision models: GPT-6 Luna Decisions, pplx-decider v1.2, drex v1.5, probed and pinned to dated snapshots (prices ~$0.00007, $0.000013, $0.000024 per call; Luna's $20 cap passes). Noul for flips, Choice for the hook, Claude Code only in the video. **The judge is Claude first;** the Gemma judge follows when the H100 frees (R5 stays blocked; X4 no longer waits on X2). **C6:** the loop grows the corpus. **New step I8:** an HF Space replay demo (published in H5). Probe spend: 9 calls, $0.00033. |
| 0c | 2026-10-19 | **Late evening: 21 steps done.** Added since 0b: **I1** HTML report (#17), **I2** Claude Code hook, advisory and cache-first (#18), **I3** `gateprobe ci` + GitHub Action (#19), **I4** Docker image, checked with `--network none` and no key (#20; it caught a git-less provenance bug, now fixed), **W2** abstract/intro/related work (#21), **W3** tool design, relations, workflow (#22; adds Newcombe 1998, verified), **W6** storyboard, voice-over, captions (#23). The paper builds at 4/4 pages, with page 4 only 6 lines of reference spillover. **The loop is now idle on human decisions:** G1 (full runs), R5 (judge hosting), C6 (corpus to 300, plus multi-operand commands), H1. **Second slip:** a red commit pushed to PR #23; the merge guard held and the lesson is updated. |
| 0b | 2026-10-19 | **Evening: 14 steps done** (E0.1 W1 S1 C1 C2 C3 R1 R2 R3 R4 C4 C5 R6 R8; PRs #1–#15). In place:
- the frozen spec and scoring rules (`docs/RELATIONS.md`: 26 transforms, matched-call floor, Newcombe intervals);
- 150 probes under 4 policies in 4 renderings, plus rule sets;
- 2,936 deterministic items in `variants/generated.jsonl` (base 150, E 809, M 227, I 725, A 1,025);
- adapters for Jev (pinned to the dated snapshot `typesafe/jev-1.14-20261014`, which the API serves for 1.14), the rule gate, the OpenAI-compatible judge and the Claude judge (Message Batches);
- the runner with cache, replay and $ cap, and the pre-registered analysis (`gateprobe analyze`).

**Live checks:** Jev in both modes, with identical calls drifting by 0.01 (floor > 0); one Claude judge call ($0.0058; about $0.003 per call at batch prices, so about $25 for the full X7 run). Spend so far is under $0.01.

**Waiting on humans:**
- **G1** (packet `docs/gates/g1-spec-freeze.md`; 8 spec choices to confirm). X1, X2, X7 and C8 wait on it.
- **R5 blocked:** H100 storage is 99% full (65 GB free; Gemma 4 31B-it bf16 is about 62 GB). Options: free space, use an FP8 checkpoint, or route the judge through OpenRouter (`google/gemma-4-31b-it` has logprobs, about $3–6).
- **C6 (corpus to 300) not started by the loop; left for the team.** It should also add multi-operand commands: `operand_order` has 0 variants today.
- **H1** (HotCRP accounts, ORCIDs).
- **Proposal:** an HF Space hosting the interactive replay demo (`HF_PERSONAL_TOKEN` is in `.env`); a new I step after I5, published by a human.

**Incident:** PR #13 was merged with a failing check (a float edge case on Linux CI); it was fixed in #14 within minutes, and the merge guard is now in `memory/lesson-gate-exit-status.md`. |
| 0 | 2026-10-19 | **Loop bootstrapped (E0.1).** Proposal frozen as `gateprobe_plan.md`; `docs/PLAN.md` maps the sprint's daily definitions of done onto steps in lanes S/C/R/X/I/W, three `[GATE]` decision points and seven `[HUMAN]` tasks; `/continue <lane>` runs one step per call. **Open for G1:** workstream owners (P1–P4); primary Jev question (Noul vs Choice); second decision model (Clef, Mercury Decide, or both); Claude Code only or OpenCode too; all four ORCIDs. **Human, later that day:** `ANTHROPIC_API_KEY` with about $200 is available for the experiments (e.g. a Claude judge), separate from the < $20 OpenRouter budget. Paper rule: one section per .tex file. **W1 reference check** (30 entries, each source-verified, in `paper/references.bib`) found where the proposal's framing differs from the sources: the OpenRouter cookbooks pin `typesafe/jev-1.13`; Jev 1.14 is out only since 14 Oct, is still `jev-preview` on TypeSafe's own API, and has no limitations page yet; of the four community projects only jevshield is a permission gate; the 0.76 → 0.48 test is a single integration test with the Jev version unstated. **Human decisions (evening):** (1) a fifth gate, the Claude judge on `claude-opus-5-5` via the Message Batches API, joins the evaluation — plan amended with R8 (backend) and X7 (pilot + 3-repeat run), X4 now waits on X7; (2) the authority and supersession work is unpublished and is **never cited or mentioned** (overrides the proposal's "cite both preprints"); (3) no branch protection on `main`; (4) Jev is pinned at **1.14** (`typesafe/jev-1.14`), not 1.13 — the paper should say the cookbooks and community gates install 1.13. **S1 merged:** package skeleton, adapter contract + fake gate, `gateprobe` CLI surface, `configs/gates.yaml` (five gates, all pinned) and `configs/run.yaml`. |
