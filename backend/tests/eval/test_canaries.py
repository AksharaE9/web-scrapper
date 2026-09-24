"""
tests/eval/test_canaries.py — Test extraction yield monitoring and canary validation (§4 P0).
"""

from __future__ import annotations

import pytest
from app.eval.canaries import (
    BASELINE_CANARIES,
    calculate_yield_metrics,
    validate_against_canaries,
)
from app.graph.state import ResolvedEntity


def test_calculate_yield_metrics_normal():
    metrics = calculate_yield_metrics(
        pages_attempted=20,
        pages_http_200=18,
        pages_with_extracted_fields=14,
    )
    assert metrics.http_success_rate == 0.90
    assert metrics.yield_rate == 0.70
    assert not metrics.silent_blockage_detected
    assert metrics.diagnostic_message is None


def test_calculate_yield_metrics_silent_blockage():
    # 20 pages attempted, 19 returned HTTP 200, but only 1 extracted field (empty shell blocking)
    metrics = calculate_yield_metrics(
        pages_attempted=20,
        pages_http_200=19,
        pages_with_extracted_fields=1,
    )
    assert metrics.http_success_rate == 0.95
    assert metrics.yield_rate == 0.05
    assert metrics.silent_blockage_detected
    assert "Silent scraper blockage detected" in metrics.diagnostic_message


def test_validate_against_canaries():
    entities = [
        ResolvedEntity(
            id="test-1",
            canonical_name="Third Wave Coffee Roasters",
            name_norm="third wave coffee roasters",
            primary_category="cafe",
            categories=["cafe", "coffee_shop"],
            website_domain="thirdwavecoffeeroasters.com",
            lon=77.62,
            lat=12.93,
        ),
        ResolvedEntity(
            id="test-2",
            canonical_name="Cult.fit Fitness Center",
            name_norm="cult fit fitness center",
            primary_category="gym",
            categories=["gym", "fitness_centre"],
            website_domain="cult.fit",
            lon=77.63,
            lat=12.92,
        ),
    ]

    res = validate_against_canaries(entities)
    assert res["canaries_checked"] == 2
    assert res["canaries_passed"] == 2
    assert res["pass_rate"] == 1.0
    assert len(res["divergences"]) == 0
