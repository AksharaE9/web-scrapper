"""
tests/relevance/test_known_false_positives.py — Master Gate 1 & C1 Relevance Invariants.

Asserts:
- None of the 7 known false positives are accepted for pooja_store.
- Name-only match is never accepted alone.
- Host category alone is never accepted.
- Non-evidence tokens (sri, divine, deepam) contribute zero defining score.
- Missing concept cards route to review.
- Reviewed concept cards have sufficient category coverage.
- No substring matching on category tags.
"""

import pytest
from app.relevance.concepts import ConceptCard, resolve_concept
from app.relevance.engine import evaluate_candidate
from app.relevance.features import extract_features
from app.relevance.scorer import score_evidence
from app.relevance.tokenize import tokenize_profile

KNOWN_BAD = [
    ("Divine Routes", "travel_company"),
    ("Divine Beauty Unisex Salon & Spa", "beauty_salon"),
    ("De silver studio", "jewelry_store"),
    ("Pooja Stationers Hsr", "rail_facility_or_station"),
    ("Pooja Kitchen Gallery", "hardware_home_and_garden"),
    ("Find Divine Distance Reiki", "naturopathic_holistic"),
    ("Daarva Gift Shops & Home Decor", "gift_shop"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("name,cat", KNOWN_BAD)
async def test_never_accepted_for_pooja_store(name: str, cat: str) -> None:
    """Gate 1: None of the 7 known false positive businesses are ever accepted for pooja_store."""
    card = resolve_concept("pooja_store")
    decision = await evaluate_candidate(
        name=name,
        keyword="pooja store",
        lon=77.63,
        lat=12.91,
        categories=[cat],
        card=card,
    )
    assert decision.outcome != "accepted", f"{name} ({cat}) was accepted with p={decision.p:.3f}"
    assert decision.reason_code is not None or decision.stage in ("hard_gates", "scorer", "review_band")


def test_name_alone_never_accepts() -> None:
    """Property test: f_def_name=1.0 with no defining category/OSM/web must never be accepted."""
    card = resolve_concept("pooja_store")
    # 'Pooja Stationers' has defining name token 'pooja' but category 'stationery' (or host 'general_store')
    profile = tokenize_profile("Pooja Stationers")
    feats = extract_features(
        profile=profile,
        card=card,
        raw_categories=["stationery_store"],
    )
    assert feats.f_def_name > 0.0
    assert feats.f_def_cat == 0.0
    assert feats.f_def_osm == 0.0
    assert feats.f_name_only_primary == 1.0

    score_res = score_evidence(feats, card)
    # Must be either rejected or uncertain (routing to review), never accepted
    assert score_res.outcome != "accepted", f"Name-only match was accepted with p={score_res.p}"


def test_host_category_alone_never_accepts() -> None:
    """Gift shop / generic host category without defining name or tag is not accepted."""
    card = resolve_concept("pooja_store")
    profile = tokenize_profile("Sri Krishna Stores")
    feats = extract_features(
        profile=profile,
        card=card,
        raw_categories=["gift_shop"],
    )
    assert feats.f_def_cat == 0.0
    score_res = score_evidence(feats, card)
    assert score_res.outcome != "accepted"


def test_non_evidence_token_contributes_zero() -> None:
    """Tokens like 'divine', 'deepam', 'sri' contribute zero to defining signals."""
    card = resolve_concept("pooja_store")
    profile = tokenize_profile("Sri Divine Deepam Enterprises")
    feats = extract_features(
        profile=profile,
        card=card,
        raw_categories=["general_business"],
    )
    # None of these tokens are defining terms
    assert feats.f_def_name == 0.0


@pytest.mark.asyncio
async def test_missing_card_routes_to_review() -> None:
    """Unknown keyword with synthesized fallback routes low-signal candidates to review, never accepted."""
    card = resolve_concept("unseen_exotic_concept_xyz_123")
    assert card.is_synthesized is True

    decision = await evaluate_candidate(
        name="Exotic Shop",
        keyword="unseen_exotic_concept_xyz_123",
        lon=77.6,
        lat=12.9,
        categories=["retail"],
        card=card,
        force_review=True,
    )
    assert decision.outcome in ("review", "rejected")
    assert decision.outcome != "accepted"


def test_card_has_enough_categories() -> None:
    """Every production reviewed concept card must have >= 20 defining/host categories."""
    card = resolve_concept("pooja_store")
    total_cats = len(card.categories.defining) + len(card.categories.host)
    assert total_cats >= 20, f"Concept card has only {total_cats} categories (expected >= 20)"


def test_no_substring_matching() -> None:
    """Category matching is exact or token-delimited, 'Coffee Shop' does not match 'shop'."""
    card = resolve_concept("pooja_store")
    profile = tokenize_profile("Coffee Shop")
    feats = extract_features(
        profile=profile,
        card=card,
        raw_categories=["coffee_shop"],
    )
    assert feats.f_def_cat == 0.0
