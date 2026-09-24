"""
tests/unit/test_cross_encoder_health.py — Cross Encoder Health and Discrimination Tests
"""

from __future__ import annotations

import pytest
from app.relevance.concepts import resolve_concept
from app.relevance.rerank import rerank_candidate
from app.relevance.tokenize import tokenize_profile


def test_cross_encoder_discrimination():
    card = resolve_concept("hotel")

    # Obvious match
    p_hotel = tokenize_profile(
        name="The Oberoi Luxury Hotel & Resort",
        categories=["hotel", "lodging"],
        brand="Oberoi",
        osm_tags=["tourism=hotel", "stars=5"],
    )
    res_hotel = rerank_candidate(p_hotel, card, has_defining_signal=True)

    # Obvious non-match
    p_dentist = tokenize_profile(
        name="Dr. Rao Dental Clinic & Implant Center",
        categories=["dentist", "healthcare"],
        brand=None,
        osm_tags=["amenity=dentist"],
    )
    res_dentist = rerank_candidate(p_dentist, card, has_defining_signal=False)

    # Assert clear discrimination between hotel and dentist
    assert res_hotel.ce_score > res_dentist.ce_score
    assert res_hotel.ce_score >= 0.5
    assert res_dentist.ce_score < 0.5


def test_cross_encoder_serviced_apartment_lower_than_hotel():
    card = resolve_concept("hotel")

    p_hotel = tokenize_profile(
        name="Marriott Executive Hotel",
        categories=["hotel"],
        brand="Marriott",
        osm_tags=["tourism=hotel"],
    )
    p_serviced = tokenize_profile(
        name="Olive Serviced Apartments",
        categories=["serviced_apartment"],
        brand=None,
        osm_tags=["tourism=apartment"],
    )

    res_hotel = rerank_candidate(p_hotel, card, has_defining_signal=True)
    res_serviced = rerank_candidate(p_serviced, card, has_defining_signal=False)

    assert res_hotel.ce_score > res_serviced.ce_score
