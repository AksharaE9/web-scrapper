"""
R1 — Hard Gates for Candidate Veto and Immediate Rejection

Applies hard gates before feature extraction:
  0. Taxonomy Gate (token-based category matching — R0.5)
  1. outside_boundary (Point-in-polygon with 150m edge case)
  2. closed (permanently_closed / disused)
  3. user_exclude (explicit run exclude keywords)
  4. veto_term (card veto terms in name/category without defining signal)
  5. incompatible_category (token-based — fixes D3 substring match bug)
  6. incompatible_brand (brand in incompatible list)

D3 FIX: The original check `any(ic in c_clean for ic in incomp_cats)` was a
substring match. This caused `professional_services` to match `service` from
`hotel`'s incompatible list, producing false rejects. The new check uses
token-based matching via `taxonomy_gate.gate()` which splits on word boundaries.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
import shapely.wkt
from shapely.geometry import Point

from app.relevance.concepts import ConceptCard
from app.relevance.taxonomy_gate import TaxonomyVerdict, gate as taxonomy_gate
from app.relevance.tokenize import TokenizedProfile, sanitize_raw_text, canonicalize_token

EDGE_CASE_BUFFER_DEG = 150 / 111_000  # 150m in degrees


@dataclass
class GateResult:
    passed: bool
    reason_code: str | None = None
    detail: str | None = None
    is_edge_case: bool = False


def check_hard_gates(
    profile: TokenizedProfile,
    card: ConceptCard,
    lon: float,
    lat: float,
    boundary_wkt: str | None = None,
    operating_status: str | None = None,
    user_excludes: list[str] | None = None,
    brand: str | None = None,
    raw_categories: list[str] | None = None,
) -> GateResult:
    """Evaluate all R1 hard gates."""
    # 1. Operating status check
    if operating_status and operating_status.lower() in ("permanently_closed", "closed", "disused"):
        return GateResult(passed=False, reason_code="closed", detail="Operating status indicates closed")

    # 2. Geo boundary check
    is_edge = False
    if boundary_wkt:
        try:
            poly = shapely.wkt.loads(boundary_wkt)
            pt = Point(lon, lat)
            if not poly.contains(pt):
                # Check 150m buffer
                buffered = poly.buffer(EDGE_CASE_BUFFER_DEG)
                if buffered.contains(pt):
                    is_edge = True
                else:
                    return GateResult(
                        passed=False,
                        reason_code="outside_boundary",
                        detail=f"Coordinates ({lon:.4f}, {lat:.4f}) outside target polygon",
                    )
        except Exception:
            pass

    # 3. User Exclude Keywords
    if user_excludes:
        name_clean = profile.clean_name
        for ex in user_excludes:
            clean_ex = sanitize_raw_text(ex)
            if clean_ex and (clean_ex in name_clean or clean_ex in profile.evidence_tokens):
                return GateResult(
                    passed=False,
                    reason_code="user_exclude",
                    detail=f"Matched user exclusion: '{ex}'",
                    is_edge_case=is_edge,
                )

    # Check if any defining term is present to allow potential overrides
    defining_terms = card.get_strong_defining_terms()
    has_defining_term = False
    for dt in defining_terms:
        if dt in profile.evidence_tokens or dt in profile.clean_name:
            has_defining_term = True
            break
        for bg in profile.name_bigrams:
            if dt in bg:
                has_defining_term = True
                break

    # 4. Incompatible Brand Check
    if brand:
        b_clean = sanitize_raw_text(brand)
        for incomp_brand in card.brands.incompatible:
            if sanitize_raw_text(incomp_brand) in b_clean:
                return GateResult(
                    passed=False,
                    reason_code="incompatible_brand",
                    detail=f"Incompatible brand: '{brand}'",
                    is_edge_case=is_edge,
                )

    # 5. Taxonomy Gate — token-based category matching (D3 fix)
    # Replaces the old substring match: `any(ic in c_clean for ic in incomp_cats)`
    # which caused `professional_services` to match `service` from `service_apartment`.
    #
    # The taxonomy gate returns REJECT only when a category token-set exactly
    # intersects an incompatible category token-set WITHOUT a defining override.
    if raw_categories and not card.is_synthesized:
        tax_result = taxonomy_gate(raw_categories=raw_categories, card=card)
        if tax_result.verdict == TaxonomyVerdict.REJECT and not has_defining_term:
            return GateResult(
                passed=False,
                reason_code="incompatible_category",
                detail=tax_result.reason or f"Incompatible category: '{tax_result.matched_category}'",
                is_edge_case=is_edge,
            )

    # 6. Veto Term Check (if no defining term present)
    if not has_defining_term:
        veto_terms = card.get_veto_terms()
        for vt in veto_terms:
            if vt in profile.evidence_tokens or vt in profile.category_tokens or f" {vt} " in f" {profile.clean_name} ":
                return GateResult(
                    passed=False,
                    reason_code="veto_term",
                    detail=f"Matched veto term: '{vt}'",
                    is_edge_case=is_edge,
                )

    return GateResult(passed=True, is_edge_case=is_edge)
