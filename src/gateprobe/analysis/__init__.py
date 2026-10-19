"""Scores runs against their relations: the test-retest floor, flip rates above it
with Wilson 95% intervals, probability shifts, calibration, the threshold band.

Scope of v0: `stats` (Wilson, Newcombe, percentiles, clustered bootstrap),
`score` (docs/RELATIONS.md § 3, per gate), and `write` (distilled CSVs under
results/). Out of scope: rendering (I1) and CI thresholds (I3).
"""
