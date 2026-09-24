"""
app/metrics/calibration.py — Calibration diagnostics (ECE, Brier Score) and Platt Scaling.
"""

from __future__ import annotations

import math
from typing import Sequence


def compute_brier_score(probabilities: Sequence[float], ground_truth: Sequence[int]) -> float:
    """Compute Brier score (mean squared error of probabilistic predictions). Lower is better."""
    if not probabilities or len(probabilities) != len(ground_truth):
        return 0.0
    n = len(probabilities)
    return sum((p - y) ** 2 for p, y in zip(probabilities, ground_truth)) / float(n)


def compute_expected_calibration_error(
    probabilities: Sequence[float],
    ground_truth: Sequence[int],
    num_bins: int = 10,
) -> float:
    """
    Compute Expected Calibration Error (ECE).
    Bins predictions into M equal intervals and measures weighted average gap
    between confidence and actual accuracy.
    """
    if not probabilities or len(probabilities) != len(ground_truth):
        return 0.0

    n = len(probabilities)
    bin_size = 1.0 / num_bins
    ece = 0.0

    for i in range(num_bins):
        bin_lower = i * bin_size
        bin_upper = (i + 1) * bin_size

        # Find items in bin
        bin_indices = [
            idx for idx, p in enumerate(probabilities)
            if (bin_lower <= p < bin_upper) or (i == num_bins - 1 and p == 1.0)
        ]

        if not bin_indices:
            continue

        bin_count = len(bin_indices)
        avg_confidence = sum(probabilities[idx] for idx in bin_indices) / float(bin_count)
        avg_accuracy = sum(ground_truth[idx] for idx in bin_indices) / float(bin_count)

        ece += (bin_count / float(n)) * abs(avg_accuracy - avg_confidence)

    return round(ece, 4)
