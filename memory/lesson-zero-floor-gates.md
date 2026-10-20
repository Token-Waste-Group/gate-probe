# Lesson: on a zero-floor gate, the δ-based secondaries count any movement

**Type:** lesson (X3, X4, 2026-10-20). **Audience:** every Claude scoring or writing about a run.

The three Decisions API models (Luna, pplx-decider, drex) answer identical repeats identically: f = 0 and δ = 0. The pre-registered rules then turn maximally strict:

- **S** (|Δp| > δ) counts *any* change in p_block. pplx reaches S = 100% at a 0.023 mean |Δp|.
- **The M predicate** `p(y) < p(x) − δ` counts any p decrease. Luna, pplx and drex were labelled M positive (B), with 8, 38 and 46 inversions, but only 0, 1 and 1 of those move the verdict.
- The primary flip tests are unaffected; with f = 0, F − f is simply F.

**How to apply:**
- Never re-label; the rules are pre-registered.
- Do report the verdict-level count next to the label. `relations.csv` carries it as `verdict_inversions` (M) and `flips_stricter` / `flips_looser` (E, I, A, P).
- Say "answers repeats identically", not "deterministic". Provider-side caching (RELATIONS § 5, the first known threat) gives the same picture from outside.

See [[decision-research-discipline]].
