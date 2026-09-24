"""
app/metrics/wilson.py — Wilson score interval for binomial proportions (e.g. Precision / Recall).
"""

from __future__ import annotations

import math


def compute_wilson_interval(successes: int, total: int, confidence: float = 0.95) -> tuple[float, float, float]:
    """
    Compute Wilson score interval for binomial proportion.
    Returns: (point_estimate, lower_bound, upper_bound)
    """
    if total <= 0:
        return (0.0, 0.0, 0.0)

    p = successes / float(total)
    z = 1.95996  # 95% confidence z-score

    z2 = z * z
    denominator = 1 + z2 / total
    centre = (p + z2 / (2 * total)) / denominator
    spread = z * math.sqrt((p * (1 - p) + z2 / (4 * total)) / total) / denominator

    lower = max(0.0, centre - spread)
    upper = min(1.0, centre + spread)
    return (round(p, 4), round(lower, 4), round(upper, 4))
