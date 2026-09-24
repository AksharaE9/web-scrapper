"""
tests/relevance/test_gates.py — Unit tests for hard relevance gates R1.

Mutation Requirement:
Temporarily disabling the veto override check must fail test_veto_with_defining_signal_override.
"""

from __future__ import annotations

import pytest
from app.relevance.concepts import resolve_concept
from app.relevance.gates import check_hard_gates
from app.relevance.tokenize import tokenize_profile


def test_hard_gate_closed_business() -> None:
    card = resolve_concept("pooja_store")
    profile = tokenize_profile("Sri Vinayaka Pooja Stores")
    gate_res = check_hard_gates(
        profile=profile,
        card=card,
        lon=77.75,
        lat=12.97,
        operating_status="permanently_closed",
    )
    assert not gate_res.passed
    assert gate_res.reason_code == "closed"


def test_hard_gate_veto_term() -> None:
    card = resolve_concept("pooja_store")
    # Divine Footwear has veto term 'footwear' and no defining terms
    profile = tokenize_profile("Divine Footwear")
    gate_res = check_hard_gates(
        profile=profile,
        card=card,
        lon=77.75,
        lat=12.97,
    )
    assert not gate_res.passed
    assert gate_res.reason_code == "veto_term"


def test_veto_with_defining_signal_override() -> None:
    card = resolve_concept("pooja_store")
    # A store named 'Pooja Footwear and Samagri Stores' has defining 'pooja' and veto 'footwear'
    # Defining signal must override veto to allow nuanced evaluation in R2/R4
    profile = tokenize_profile("Pooja Footwear and Samagri Stores")
    gate_res = check_hard_gates(
        profile=profile,
        card=card,
        lon=77.75,
        lat=12.97,
    )
    assert gate_res.passed, "Defining term should prevent hard-veto rejection"


def test_incompatible_brand_veto() -> None:
    card = resolve_concept("pooja_store")
    profile = tokenize_profile("William Penn Pens")
    gate_res = check_hard_gates(
        profile=profile,
        card=card,
        lon=77.75,
        lat=12.97,
        brand="William Penn",
    )
    assert not gate_res.passed
    assert gate_res.reason_code in ("incompatible_brand", "veto_term")
