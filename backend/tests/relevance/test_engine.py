"""
Relevance Cascade Unit Tests — Testing False Positives vs True Positives
Verifies that William Penn, Ximi Vogue, Divine Footwear, Archies, and Deepam Taxi
are rejected and never accepted.
"""

import pytest
from app.relevance.engine import evaluate_candidate
from app.relevance.concepts import resolve_concept

@pytest.mark.asyncio
async def test_pooja_whitefield_false_positives_vetoed() -> None:
    card = resolve_concept("pooja stores")

    # 1. William Penn
    res_wp = await evaluate_candidate(
        name="William Penn",
        keyword="pooja stores",
        lon=77.75,
        lat=12.97,
        categories=["stationery_store", "pen_shop", "gift_shop"],
        brand="William Penn",
        card=card,
    )
    assert res_wp.outcome != "accepted", f"William Penn must not be accepted, got: {res_wp.outcome}"
    assert res_wp.outcome in ("rejected", "review")

    # 2. Ximi Vogue
    res_xv = await evaluate_candidate(
        name="Ximi Vogue",
        keyword="pooja stores",
        lon=77.75,
        lat=12.97,
        categories=["fashion_accessories", "gift_shop"],
        brand="Ximi Vogue",
        card=card,
    )
    assert res_xv.outcome != "accepted", f"Ximi Vogue must not be accepted, got: {res_xv.outcome}"
    assert res_xv.outcome in ("rejected", "review")

    # 3. Divine Footwear
    res_df = await evaluate_candidate(
        name="Divine Footwear",
        keyword="pooja stores",
        lon=77.75,
        lat=12.97,
        categories=["shoe_store", "general_store"],
        card=card,
    )
    assert res_df.outcome != "accepted", f"Divine Footwear must not be accepted, got: {res_df.outcome}"
    assert res_df.outcome in ("rejected", "review")

    # 4. Archies
    res_ar = await evaluate_candidate(
        name="Archies",
        keyword="pooja stores",
        lon=77.75,
        lat=12.97,
        categories=["gift_shop", "greeting_cards"],
        brand="Archies",
        card=card,
    )
    assert res_ar.outcome != "accepted", f"Archies must not be accepted, got: {res_ar.outcome}"
    assert res_ar.outcome in ("rejected", "review")

    # 5. Deepam Taxi
    res_dt = await evaluate_candidate(
        name="Deepam Taxi",
        keyword="pooja stores",
        lon=77.75,
        lat=12.97,
        categories=["taxi_service", "travel_agency"],
        card=card,
    )
    assert res_dt.outcome != "accepted", f"Deepam Taxi must not be accepted, got: {res_dt.outcome}"
    assert res_dt.outcome in ("rejected", "review")


@pytest.mark.asyncio
async def test_genuine_pooja_stores_accepted() -> None:
    card = resolve_concept("pooja stores")

    # Genuine True Positive
    res_true = await evaluate_candidate(
        name="Sri Lakshmi Pooja Stores",
        keyword="pooja stores",
        lon=77.75,
        lat=12.97,
        categories=["religious_goods_store", "general_store"],
        card=card,
    )
    assert res_true.outcome == "accepted", f"Expected Sri Lakshmi Pooja Stores to be accepted, got: {res_true.outcome}"
    assert res_true.p >= 0.70
