"""
tests/relevance/test_features.py — Feature vector schema completeness and structural rules.
"""

from __future__ import annotations

import pytest
from app.relevance.concepts import resolve_concept
from app.relevance.features import extract_features
from app.relevance.scorer import score_evidence
from app.relevance.tokenize import tokenize_profile


def test_feature_vector_bounded_and_complete() -> None:
    card = resolve_concept("pooja_store")
    profile = tokenize_profile("Sri Lakshmi Pooja Stores", categories=["gift_shop"])
    features = extract_features(profile=profile, card=card)
    feat_dict = features.to_dict()

    expected_keys = {
        "f_def_name", "f_def_cat", "f_def_osm", "f_def_web",
        "f_sup_count", "f_host_cat", "f_nonev_only", "f_cat_conf",
    }
    present_keys = set(feat_dict.keys())
    assert expected_keys.issubset(present_keys), f"Missing expected feature keys: {expected_keys - present_keys}"

    for k, v in feat_dict.items():
        assert isinstance(v, (int, float)), f"Feature {k} is not numeric: {v}"
        assert -5.0 <= v <= 10.0, f"Feature {k} out of bounds: {v}"


def test_structural_rule_zero_defining_signal_never_accepted() -> None:
    """
    CRITICAL STRUCTURAL RULE:
    When require_defining_signal=True, if f_def_name == f_def_cat == f_def_osm == f_def_web == 0,
    the logistic scorer MUST NEVER produce an accepted verdict, regardless of other features.
    """
    card = resolve_concept("pooja_store")
    # Store with host category only and zero defining signals (e.g., Archies gift shop)
    profile = tokenize_profile("Archies Gallery", categories=["gift_shop"])
    features = extract_features(profile=profile, card=card)

    assert features.f_def_name == 0.0
    assert features.f_def_cat == 0.0
    assert features.f_def_osm == 0.0
    assert features.f_def_web == 0.0

    res = score_evidence(features, card)
    assert res.outcome != "accepted", f"Expected non-accepted outcome for zero defining signals, got {res.outcome} (p={res.p})"
