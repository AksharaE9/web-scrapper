"""
app/eval/canaries.py — Extraction yield monitoring and canary validation (§4 P0).

Catches silent scraping breakage by verifying extraction yield and comparing against
known-correct canary POI records.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CanaryPOI:
    canonical_name: str
    locality: str
    city: str
    expected_primary_category: str
    expected_categories: list[str] = field(default_factory=list)
    expected_phone_prefix: str | None = None
    expected_domain: str | None = None


# Known-correct baseline canaries across key categories in Indian metros
BASELINE_CANARIES: list[CanaryPOI] = [
    CanaryPOI(
        canonical_name="Third Wave Coffee",
        locality="Koramangala",
        city="Bengaluru",
        expected_primary_category="cafe",
        expected_categories=["cafe", "coffee_shop", "restaurant"],
        expected_domain="thirdwavecoffeeroasters.com",
    ),
    CanaryPOI(
        canonical_name="Cult.fit",
        locality="HSR Layout",
        city="Bengaluru",
        expected_primary_category="gym",
        expected_categories=["gym", "fitness_centre", "sports_club"],
        expected_domain="cult.fit",
    ),
    CanaryPOI(
        canonical_name="Giri Trading Agency",
        locality="Malleswaram",
        city="Bengaluru",
        expected_primary_category="religious_goods_store",
        expected_categories=["religious_goods_store", "general_store", "gift_shop"],
        expected_domain="giri.in",
    ),
    CanaryPOI(
        canonical_name="Toit Brewpub",
        locality="Indiranagar",
        city="Bengaluru",
        expected_primary_category="brewery",
        expected_categories=["brewery", "pub", "restaurant", "bar"],
        expected_domain="toit.in",
    ),
    CanaryPOI(
        canonical_name="CTR Shri Sagar",
        locality="Malleswaram",
        city="Bengaluru",
        expected_primary_category="restaurant",
        expected_categories=["restaurant", "south_indian_restaurant", "cafe"],
    ),
]


@dataclass
class YieldMetrics:
    pages_attempted: int
    pages_http_200: int
    pages_with_extracted_fields: int
    http_success_rate: float
    yield_rate: float
    silent_blockage_detected: bool
    diagnostic_message: str | None = None


def calculate_yield_metrics(
    pages_attempted: int,
    pages_http_200: int,
    pages_with_extracted_fields: int,
) -> YieldMetrics:
    """
    Calculate http_success_rate and extraction yield_rate.
    Detects silent bot blockages where HTTP is 200 (empty HTML/SPA shell) but extraction yields 0 fields.
    """
    if pages_attempted <= 0:
        return YieldMetrics(
            pages_attempted=0,
            pages_http_200=0,
            pages_with_extracted_fields=0,
            http_success_rate=1.0,
            yield_rate=1.0,
            silent_blockage_detected=False,
        )

    http_rate = pages_http_200 / pages_attempted
    yield_rate = pages_with_extracted_fields / max(pages_attempted, 1)

    # Silent breakage: HTTP 200 is high (>=80%) but field yield collapsed (<=15%) on >=5 pages
    silent_blockage = (pages_attempted >= 5 and http_rate >= 0.80 and yield_rate <= 0.15)
    diag = None
    if silent_blockage:
        diag = (
            f"Silent scraper blockage detected: {pages_http_200}/{pages_attempted} pages returned HTTP 200, "
            f"but only {pages_with_extracted_fields} produced structured fields (yield {yield_rate:.1%})."
        )

    return YieldMetrics(
        pages_attempted=pages_attempted,
        pages_http_200=pages_http_200,
        pages_with_extracted_fields=pages_with_extracted_fields,
        http_success_rate=round(http_rate, 3),
        yield_rate=round(yield_rate, 3),
        silent_blockage_detected=silent_blockage,
        diagnostic_message=diag,
    )


def validate_against_canaries(
    extracted_entities: list[Any],
    canaries: list[CanaryPOI] | None = None,
) -> dict[str, Any]:
    """Check whether known canaries present in the dataset meet expected field consistency."""
    benchmark = canaries or BASELINE_CANARIES
    matches_tested = 0
    matches_passed = 0
    divergence_details: list[dict[str, Any]] = []

    for canary in benchmark:
        # Find matching extracted entity by name + city/locality
        matched_ent = None
        for ent in extracted_entities:
            ent_name = (getattr(ent, "canonical_name", "") or getattr(ent, "name", "") or "").lower()
            if canary.canonical_name.lower() in ent_name:
                matched_ent = ent
                break

        if not matched_ent:
            continue

        matches_tested += 1
        issues = []
        # Check category
        ent_cats = getattr(matched_ent, "categories", []) or []
        ent_primary = getattr(matched_ent, "primary_category", "") or ""
        cat_match = (
            canary.expected_primary_category in ent_primary
            or any(c in ent_cats for c in canary.expected_categories)
        )
        if not cat_match:
            issues.append(f"Category mismatch: expected {canary.expected_primary_category}, got {ent_primary}")

        # Check domain
        if canary.expected_domain:
            ent_dom = getattr(matched_ent, "website_domain", "") or ""
            if canary.expected_domain not in ent_dom:
                issues.append(f"Domain mismatch: expected {canary.expected_domain}, got {ent_dom}")

        if not issues:
            matches_passed += 1
        else:
            divergence_details.append({
                "canary": canary.canonical_name,
                "issues": issues,
            })

    pass_rate = (matches_passed / matches_tested) if matches_tested > 0 else 1.0
    return {
        "canaries_checked": matches_tested,
        "canaries_passed": matches_passed,
        "pass_rate": round(pass_rate, 3),
        "divergences": divergence_details,
    }
