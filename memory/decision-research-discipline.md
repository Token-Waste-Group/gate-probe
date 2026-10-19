# Decision: evaluation discipline — frozen scope, human gates, noise floors, provenance

**Type:** decision. **Audience:** every Claude in this repo.

These rules keep the demo's claims reviewable on a five-day clock
(`gateprobe_plan.md`). They are hard invariants, mirrored in `CLAUDE.md`:

- **Scope is frozen:** relation classes E, M, I, A, P; RQ1–RQ4; the gates
  fixed at G1 (Jev 1.14, GPT-6 Luna Decisions, pplx-decider v1.2, drex v1.5,
  the Claude Opus 5.5 judge, the rule gate; the Gemma judge when the H100
  frees); three figures. No relation class after G1 (Mon 19 18:00). Stretch items
  (P sandbox validation, OpenCode plugin, PolicyForge) only after G2 says full.
- **Decision points are human decisions.** G1 spec freeze, G2 go/no-go (full /
  reduced / pivot to ToolSense), G3 results freeze (Thu 22 12:00), and every
  fallback in the risk table. The loop reports and recommends; it never
  decides. Do not negotiate with sunk cost.
- **Oracle-free, pre-registered scoring.** E/M/I/A generators are deterministic
  and seeded; violation predicates, the floor and the "violated" rule are
  written in `docs/RELATIONS.md` before any run and never relaxed after. P is
  always reported apart from E so a flip can't be blamed on a bad paraphrase.
  Hand labels feed the calibration figure only.
- **Noise floor first.** Measure each gate's test–retest floor from identical
  repeats (3; 5 if the floor exceeds 10%); report flips above it, with Wilson
  95% intervals and n on every number.
- **Provenance on everything:** pinned model ids (`typesafe/jev-1.14-20261014`), git
  hash + config hash + gate + model + repeat index on every row; the
  content-addressed cache (repeat index in the key) is the source of truth and
  the replay mode.
- **Budget:** $ cap from config on every API path, spend logged; OpenRouter
  under $20 (price-check GPT-6 Luna Decisions before any run); Claude about
  $200 in total — see [[decision-llm-routing]].
- **Negative results are committed** as `docs/experiments/` reports. E flips
  at the floor is a publishable outcome — the plan leads with M and A then.
- **Prior work:** the authority and supersession work is unpublished — never
  cite or mention it in the paper, video or public release (human rule,
  2026-10-19, overriding the proposal); lift no tool details; keep systematic
  findings for the planned A\* paper.

**How to apply:** before any relation, analysis or run change, re-read the
relevant `gateprobe_plan.md` section and `docs/RELATIONS.md`; push the planned
report before running; update `STATUS.md` the same day; if a result trips a
fallback trigger, surface it to the humans immediately — see
[[decision-autonomy-loop]] and [[decision-llm-routing]].
