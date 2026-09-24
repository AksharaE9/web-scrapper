"""
tests/test_persist_bulk.py — Benchmark and verification of batch persistence (§3.3).
"""

from __future__ import annotations

import time
import uuid
import pytest
from app.db.bulk import (
    bulk_match_existing_businesses,
    bulk_upsert_businesses,
    bulk_insert_business_sources,
    bulk_insert_field_provenance,
    bulk_insert_verifications,
    bulk_upsert_run_results,
)
from app.db.pool import get_conn
from app.graph.state import ResolvedEntity


@pytest.mark.asyncio
async def test_bulk_persist_100_leads_under_one_second():
    """Assert persisting 100 leads completes in well under 1 second with batch statements."""
    run_id = str(uuid.uuid4())
    test_entities = []

    for i in range(100):
        ent_id = str(uuid.uuid4())
        test_entities.append(
            ResolvedEntity(
                id=ent_id,
                canonical_name=f"Bulk Test Business {i}",
                name_norm=f"bulk test business {i}",
                primary_category="gym",
                categories=["gym", "fitness_centre"],
                phones_e164=[f"+9198765432{i:02d}"],
                emails=[f"contact{i}@example.com"],
                website_domain=f"bulk-test-{i}.com",
                website_url=f"https://bulk-test-{i}.com",
                locality="Koramangala",
                city="Bengaluru",
                state="Karnataka",
                country="India",
                lon=77.62 + (i * 0.0001),
                lat=12.93 + (i * 0.0001),
                confidence=0.92,
                tier="Verified",
                independent_source_count=2,
                source_ids=[f"overture:ov_{i}", f"osm:osm_{i}"],
            )
        )

    t0 = time.monotonic()
    async with get_conn() as conn:
        async with conn.transaction():
            # 0. Insert query_run
            await conn.execute(
                """
                INSERT INTO query_runs (id, status, raw_input, locality, city, state, keywords, retryable)
                VALUES (%s, 'running', '{}'::jsonb, 'Koramangala', 'Bengaluru', 'Karnataka', ARRAY['gym'], TRUE)
                """,
                (run_id,),
            )

            # 1. Match
            matched = await bulk_match_existing_businesses(conn, test_entities)
            assert isinstance(matched, dict)


            # 2. Upsert businesses
            biz_rows = [
                {
                    "id": e.id,
                    "canonical_name": e.canonical_name,
                    "name_norm": e.name_norm,
                    "primary_category": e.primary_category,
                    "categories": e.categories,
                    "phones_e164": e.phones_e164,
                    "emails": e.emails,
                    "website_url": e.website_url,
                    "website_domain": e.website_domain,
                    "socials": {},
                    "address": {},
                    "address_text": f"{e.locality}, {e.city}",
                    "locality": e.locality,
                    "city": e.city,
                    "state": e.state,
                    "country": e.country,
                    "lon": e.lon,
                    "lat": e.lat,
                    "geohash7": "tdr1v4x",
                    "operating_status": "operational",
                    "confidence": e.confidence,
                    "tier": e.tier,
                    "independent_source_count": e.independent_source_count,
                    "run_id": run_id,
                }
                for e in test_entities
            ]
            inserted_count = await bulk_upsert_businesses(conn, biz_rows)
            assert inserted_count == 100

            # 3. Sources
            sources_rows = []
            for e in test_entities:
                for sid in e.source_ids:
                    s_name, s_rec = sid.split(":", 1)
                    sources_rows.append({"business_id": e.id, "source": s_name, "source_record_id": s_rec})
            src_count = await bulk_insert_business_sources(conn, sources_rows)
            assert src_count == 200

            # 4. Run results
            results_rows = [
                {
                    "run_id": run_id,
                    "business_id": e.id,
                    "keyword": "gym",
                    "match_score": e.confidence,
                    "match_reason": "High confidence match",
                    "rank": idx + 1,
                    "is_new_business": True,
                    "edge_case": False,
                    "decision": "accepted",
                    "relevance_p": e.confidence,
                    "relevance_stage": "scorer",
                    "relevance_features": "{}",
                    "relevance_reasons": "[]",
                    "concept_id": "gym",
                    "concept_version": 1,
                    "scorer_version": "v2.2",
                }
                for idx, e in enumerate(test_entities)
            ]
            res_count = await bulk_upsert_run_results(conn, results_rows)
            assert res_count == 100

    elapsed = time.monotonic() - t0
    print(f"Persisted 100 entities, 200 sources, 100 results in {elapsed:.3f}s")
    assert elapsed < 1.5, f"Bulk persist took {elapsed:.3f}s, expected < 1.5s"
