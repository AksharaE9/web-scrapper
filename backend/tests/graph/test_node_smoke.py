"""
Isolated Node Smoke Test Suite

Executes unit/smoke tests for nodes N4, N5, N6, N7, N8, N10
with offline fixtures, zero external network calls, executing in < 5 seconds.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.graph.nodes import (
    n4_filter,
    n5_resolve,
    n6_enrich,
    n7_verify,
    n8_score,
    n10_persist,
)
from app.graph.state import (
    CheckResult,
    GeoResolution,
    LocationInput,
    QueryInput,
    RawCandidate,
    ResolvedEntity,
    RunState,
)
from app.resolve.geo_math import haversine_distance_m


@pytest.fixture
def sample_geo() -> GeoResolution:
    return GeoResolution(
        display_name="HSR Layout, Bengaluru, Karnataka, India",
        osm_id="seed/HSR Layout",
        polygon_wkt="POLYGON((77.62 12.89, 77.66 12.89, 77.66 12.93, 77.62 12.93, 77.62 12.89))",
        boundary_kind="buffered_point",
        bbox=(77.62, 12.89, 77.66, 12.93),
        centroid=(77.6393, 12.9121),
        geo_confidence=0.95,
        alternatives=[],
    )


@pytest.fixture
def sample_raw_candidates() -> list[RawCandidate]:
    return [
        RawCandidate(
            source="overture",
            source_record_id="ov_1",
            name="Sri Lakshmi Pooja Stores",
            lon=77.6395,
            lat=12.9125,
            categories=["pooja_store", "religious_goods"],
            phones=["+918025551234"],
            websites=["https://srilakshmipooja.com"],
            address={"locality": "HSR Layout", "city": "Bengaluru"},
            raw={"name": "Sri Lakshmi Pooja Stores"},
        ),
        RawCandidate(
            source="osm",
            source_record_id="osm_1",
            name="Divine Footwear & Shoes",
            lon=77.6390,
            lat=12.9120,
            categories=["shoe_store"],
            phones=[],
            websites=[],
            address={"locality": "HSR Layout", "city": "Bengaluru"},
            raw={"name": "Divine Footwear & Shoes", "shop": "shoes"},
        ),
    ]


@pytest.mark.asyncio
async def test_n4_relevance_smoke(sample_geo: GeoResolution, sample_raw_candidates: list[RawCandidate]) -> None:
    """N4 CandidateFilter smoke test: authenticates true pooja store, filters out footwear."""
    state: RunState = {
        "run_id": "test_run_n4",
        "query": QueryInput(keywords=["pooja store"], location=LocationInput(locality="HSR Layout", city="Bengaluru")),
        "geo": sample_geo,
        "candidates": sample_raw_candidates,
    }

    with patch("app.graph.nodes.n4_relevance.bulk_insert_rejected_candidates", new=AsyncMock()):
        with patch("app.graph.nodes.n4_relevance.get_conn") as mock_conn:
            mock_ctx = AsyncMock()
            mock_conn.return_value.__aenter__.return_value = mock_ctx
            res = await n4_filter.run(state)

    passed = res.get("candidates", [])
    assert len(passed) == 1
    assert passed[0].name == "Sri Lakshmi Pooja Stores"
    assert "relevance_cascade" in res.get("source_stats", {})


@pytest.mark.asyncio
async def test_n5_resolve_smoke_with_haversine(sample_geo: GeoResolution) -> None:
    """N5 EntityResolverAgent smoke test: clusters duplicates and computes haversine distance."""
    c1 = RawCandidate(
        source="overture",
        source_record_id="ov_1",
        name="Sri Lakshmi Pooja Stores",
        lon=77.6395,
        lat=12.9125,
        categories=["pooja_store"],
        phones=["+918025551234"],
        websites=["https://srilakshmipooja.com"],
        address={"locality": "HSR Layout", "city": "Bengaluru"},
        raw={"geohash7": "tdr1v7m"},
    )
    c2 = RawCandidate(
        source="osm",
        source_record_id="osm_1",
        name="Sri Lakshmi Pooja Store",
        lon=77.6396,
        lat=12.9126,
        categories=["pooja_goods"],
        phones=["08025551234"],
        websites=["https://srilakshmipooja.com/contact"],
        address={"locality": "HSR Layout", "city": "Bengaluru"},
        raw={"geohash7": "tdr1v7m"},
    )

    state: RunState = {
        "run_id": "test_run_n5",
        "geo": sample_geo,
        "candidates": [c1, c2],
    }

    res = await n5_resolve.run(state)
    entities = res.get("entities", [])
    assert len(entities) == 1
    ent = entities[0]
    assert "Sri Lakshmi Pooja" in ent.canonical_name
    assert ent.distance_m is not None
    assert ent.distance_m >= 0.0
    # Direct haversine sanity
    expected_dist = round(haversine_distance_m(ent.lon, ent.lat, sample_geo.centroid[0], sample_geo.centroid[1]), 1)
    assert ent.distance_m == expected_dist


@pytest.mark.asyncio
async def test_n6_enrich_smoke() -> None:
    """N6 WebsiteEnrichmentAgent smoke test with mocked crawler."""
    ent = ResolvedEntity(
        id="ent_1",
        canonical_name="Test Store",
        name_norm="test store",
        primary_category="Retail",
        lon=77.6395,
        lat=12.9125,
        website_url="https://teststore.com",
        phones_e164=[],
        emails=[],
        socials={},
    )
    state: RunState = {
        "run_id": "test_run_n6",
        "query": QueryInput(keywords=["retail"], location=LocationInput(city="Bengaluru"), enrich_websites=True),
        "entities": [ent],
    }

    mock_crawl_result = MagicMock(
        outcome="ok",
        url="https://teststore.com",
        html="<html><body><a href='tel:+919876543210'>Call Us</a><a href='mailto:info@teststore.com'>Email</a></body></html>",
    )

    with patch("app.crawl.frontier.DomainFrontier.crawl_domain", new=AsyncMock(return_value=[mock_crawl_result])):
        res = await n6_enrich.run(state)

    entities = res.get("entities", [])
    assert len(entities) == 1
    assert "+919876543210" in entities[0].phones_e164
    assert "info@teststore.com" in entities[0].emails


@pytest.mark.asyncio
async def test_n7_verify_smoke(sample_geo: GeoResolution) -> None:
    """N7 VerificationAgent smoke test."""
    ent = ResolvedEntity(
        id="ent_1",
        canonical_name="Sri Lakshmi Pooja Stores",
        name_norm="sri lakshmi pooja stores",
        primary_category="pooja_store",
        lon=77.6395,
        lat=12.9125,
        phones_e164=["+918025551234"],
        emails=["contact@lakshmistore.in"],
        website_url="https://lakshmistore.in",
        locality="HSR Layout",
        city="Bengaluru",
    )

    state: RunState = {
        "run_id": "test_run_n7",
        "geo": sample_geo,
        "query": QueryInput(keywords=["pooja"], location=LocationInput(locality="HSR Layout", city="Bengaluru")),
        "entities": [ent],
    }

    mock_checks = [
        CheckResult(check_name="phone_valid", outcome="passed", detail={"detail": "+918025551234"}),
        CheckResult(check_name="point_in_polygon", outcome="passed", detail={"detail": "within"}),
    ]

    with patch("app.graph.nodes.n7_verify.run_entity_verification_checks", new=AsyncMock(return_value=mock_checks)):
        res = await n7_verify.run(state)

    verifs = res.get("verifications", {})
    assert "ent_1" in verifs
    assert len(verifs["ent_1"]) == 2


@pytest.mark.asyncio
async def test_n8_score_smoke() -> None:
    """N8 ConfidenceScorer smoke test."""
    ent = ResolvedEntity(
        id="ent_1",
        canonical_name="Verified Store",
        name_norm="verified store",
        primary_category="Retail",
        lon=77.6395,
        lat=12.9125,
        distance_m=100.0,
        independent_source_count=2,
    )

    state: RunState = {
        "run_id": "test_run_n8",
        "entities": [ent],
        "verifications": {
            "ent_1": [
                CheckResult(check_name="phone_valid", outcome="passed"),
                CheckResult(check_name="multi_source_agreement", outcome="passed"),
            ]
        },
    }

    res = await n8_score.run(state)
    scored = res.get("entities", [])
    assert len(scored) == 1
    assert scored[0].confidence >= 0.60
    assert scored[0].tier in ("Verified", "Likely")


@pytest.mark.asyncio
async def test_n10_persist_smoke() -> None:
    """N10 Persister smoke test."""
    ent = ResolvedEntity(
        id="ent_1",
        canonical_name="Persisted Store",
        name_norm="persisted store",
        primary_category="Retail",
        lon=77.6395,
        lat=12.9125,
        confidence=0.85,
        tier="Verified",
        source_ids=["overture/ov_1"],
    )

    state: RunState = {
        "run_id": "test_run_n10",
        "query": QueryInput(keywords=["retail"], location=LocationInput(city="Bengaluru")),
        "entities": [ent],
    }

    with patch("app.graph.nodes.n10_persist.get_pool") as mock_get_pool:
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_tx = AsyncMock()
        mock_conn.transaction = MagicMock(return_value=mock_tx)
        mock_cursor = AsyncMock()
        mock_cursor.fetchone.return_value = None  # No duplicate found
        mock_cursor.__aenter__.return_value = mock_cursor
        mock_conn.execute.return_value = mock_cursor
        mock_conn.cursor = MagicMock(return_value=mock_cursor)
        mock_pool.connection.return_value.__aenter__.return_value = mock_conn
        mock_get_pool.return_value = mock_pool

        res = await n10_persist.run(state)

    assert "entities" in res
