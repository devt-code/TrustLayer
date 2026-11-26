"""Small statistics helpers, standard library only."""

from __future__ import annotations

import math
from collections.abc import Sequence

Z95 = 1.959963984540054  # the z-score for a two-sided 95% interval


def wilson_interval(successes: int, total: int, z: float = Z95) -> tuple[float, float]:
    """A 95% confidence interval for a rate, by the Wilson score method.

    With few trials a bare percentage hides how unsure it is. For example, 10 out of 10
    fits a true rate anywhere from about 72% to 100%.
    """
    if total <= 0:
        return (0.0, 1.0)
    if not 0 <= successes <= total:
        raise ValueError("successes must be between 0 and total")
    p = successes / total
    z2 = z * z
    denominator = 1 + z2 / total
    center = (p + z2 / (2 * total)) / denominator
    half = z * math.sqrt(p * (1 - p) / total + z2 / (4 * total * total)) / denominator
    low = 0.0 if successes == 0 else max(0.0, center - half)
    high = 1.0 if successes == total else min(1.0, center + half)
    return (low, high)


def percentile(values: Sequence[float], q: float) -> float | None:
    """The q-th percentile (0 to 100) by the nearest-rank method. None if there's no data."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(q * len(ordered) / 100))
    return ordered[rank - 1]
