# STATUS — one line per day + every decision-point outcome

Convention: updated every evening; decision points (G1 Mon 19 18:00, G2 Wed 21
18:00, G3 Thu 22 12:00) and fallback triggers are recorded here the day they
happen, never silently. Newest first. Day 0 = Mon 19 Oct 2026. Submit Fri 23
Oct evening; hard stop Sat 24 Oct 13:59 CEST / 14:59 MSK (AoE).

| Day | Date | Log |
|-----|------------|-----|
| 0 | 2026-10-19 | **Loop bootstrapped (E0.1).** Proposal frozen as `gateprobe_plan.md`; `docs/PLAN.md` maps the sprint's daily definitions of done onto steps in lanes S/C/R/X/I/W, three `[GATE]` decision points and seven `[HUMAN]` tasks; `/continue <lane>` runs one step per call. **Open for G1:** workstream owners (P1–P4); primary Jev question (Noul vs Choice); second decision model (Clef, Mercury Decide, or both); Claude Code only or OpenCode too; all four ORCIDs. **Human, later that day:** `ANTHROPIC_API_KEY` with about $200 is available for the experiments (e.g. a Claude judge), separate from the < $20 OpenRouter budget; adding a Claude-judge gate is proposed and awaits confirmation. Paper rule: one section per .tex file. **W1 reference check** (30 entries, each source-verified, in `paper/references.bib`) found where the proposal's framing differs from the sources: the OpenRouter cookbooks pin `typesafe/jev-1.13`; Jev 1.14 is out only since 14 Oct, is still `jev-preview` on TypeSafe's own API, and has no limitations page yet; of the four community projects only jevshield is a permission gate; the 0.76 → 0.48 test is a single integration test with the Jev version unstated; neither own preprint has an arXiv record. **For G1:** pin Jev 1.14 (newest) or 1.13 (what the cookbooks and gates install)? Arxiv IDs for the authority and supersession preprints, or cite them another way? |
