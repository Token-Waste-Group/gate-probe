# Lesson: when re-scoring a subset of pairs, reuse the gate's frozen floor

**Type:** lesson (X6, 2026-10-20). **Audience:** every Claude computing flip rates on part of a run.

The floor f and δ come from repeat 1 vs repeat 2 over **all** of a gate's items (`score.floor`). X6 first fed `score()` the base rows plus a subset of P rows. That silently computed a different floor, from fewer items, and moved F − f: Jev's command-rewrite row came out +3.3 instead of the frozen +3.1.

**How to apply:**
- Compute `floors = {g: floor(gate)}` from `index(all frozen rows)`.
- Call `relation_stats(index(subset_rows)[g], floors[g], cls, None, z_bonf)` with `z_bonf` from `results/x4-final/meta.csv`.
- **Check:** the "everything" subset must reproduce the frozen table row exactly, at the CSV's 6-decimal precision, before you trust any other subset.

See [[lesson-zero-floor-gates]].
