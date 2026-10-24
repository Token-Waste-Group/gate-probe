"""Interval statistics for docs/RELATIONS.md § 3: Wilson, Newcombe, percentiles, clustered bootstrap.

Scope of v0: pure-stdlib implementations with hand-checkable behavior —
Wilson score intervals, Newcombe's hybrid-score interval for a difference of
proportions (method 10, built from the two Wilson intervals), linear-
interpolation percentiles, and a percentile bootstrap over clusters (parents)
that resamples per-cluster totals. Out of scope: anything not pre-registered.
"""

from __future__ import annotations

import math
import random
from statistics import NormalDist

Z95 = NormalDist().inv_cdf(0.975)


def z_for(level: float) -> float:
    """Two-sided z for a confidence level, e.g. 0.95 -> 1.96."""
    return NormalDist().inv_cdf(1 - (1 - level) / 2)


def wilson(k: int, n: int, z: float = Z95) -> tuple[float, float, float]:
    """(estimate, lower, upper); n = 0 gives (nan, 0, 1)."""
    if n == 0:
        return math.nan, 0.0, 1.0
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    # The bounds are exactly 0 at k = 0 and exactly 1 at k = n; set them so, rather than trusting
    # floating point (CI's libm left 2.8e-17 where macOS gave 0.0).
    lo = 0.0 if k == 0 else max(0.0, centre - half)
    hi = 1.0 if k == n else min(1.0, centre + half)
    return p, lo, hi


def newcombe(k1: int, n1: int, k2: int, n2: int, z: float = Z95) -> tuple[float, float, float]:
    """Difference p1 - p2 with Newcombe's hybrid-score interval (1998, method 10)."""
    p1, l1, u1 = wilson(k1, n1, z)
    p2, l2, u2 = wilson(k2, n2, z)
    if math.isnan(p1) or math.isnan(p2):
        return math.nan, -1.0, 1.0
    d = p1 - p2
    return d, d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2), d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)


def percentile(values: list[float], q: float) -> float:
    """Linear interpolation between order statistics (numpy's default), q in [0, 100]."""
    if not values:
        return math.nan
    xs = sorted(values)
    pos = (len(xs) - 1) * q / 100
    lo, hi = math.floor(pos), math.ceil(pos)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def cluster_bootstrap(
    clusters: list[tuple[float, int]], resamples: int = 10_000, seed: int = 13, level: float = 0.95
) -> tuple[float, float, float]:
    """Mean of a per-item quantity, clustered: `clusters` holds (sum over the cluster's items, item count).

    Returns (estimate, lower, upper), the percentile interval over resampled clusters.
    """
    total_n = sum(n for _, n in clusters)
    if not clusters or total_n == 0:
        return math.nan, math.nan, math.nan
    estimate = sum(s for s, _ in clusters) / total_n
    rng = random.Random(seed)
    m = len(clusters)
    stats = []
    for _ in range(resamples):
        s = n = 0.0
        for _ in range(m):
            cs, cn = clusters[rng.randrange(m)]
            s += cs
            n += cn
        if n:
            stats.append(s / n)
    alpha = (1 - level) / 2 * 100
    return estimate, percentile(stats, alpha), percentile(stats, 100 - alpha)
