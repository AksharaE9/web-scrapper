"""
app/db/bulk.py — High-throughput batch inserts, matching, and upserts for persistence nodes.

Replaces row-by-row Python loops with batch parameterized statements.
"""

from __future__ import annotations

import json
import logging
from typing import Any
import uuid
import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

logger = logging.getLogger(__name__)


async def bulk_match_existing_businesses(
    conn: psycopg.AsyncConnection[Any],
    entities: list[Any],
) -> dict[int, uuid.UUID]:
    """
    Batch find existing business matches for a list of ResolvedEntities.
    Returns: mapping from entity index in list to existing business_id UUID.
    Uses:
      1. Batch lookup on (source, source_record_id) in business_sources
      2. Batch lookup on website_domain in businesses
      3. Batch lookup on phones_e164 in businesses
      4. Targeted spatial match for remaining unmatched entities
    """
    matched: dict[int, uuid.UUID] = {}
    if not entities:
        return matched

    # 1. Source IDs batch lookup
    source_pairs: list[tuple[int, str, str]] = []
    for idx, e in enumerate(entities):
        for sid in getattr(e, "source_ids", []) or []:
            if ":" in sid:
                s_name, s_rec = sid.split(":", 1)
                source_pairs.append((idx, s_name, s_rec))

    if source_pairs:
        # Group source pairs to query in batch
        src_names = [p[1] for p in source_pairs]
        src_recs = [p[2] for p in source_pairs]
        res = await conn.execute(
            """
            SELECT bs.business_id, bs.source, bs.source_record_id
            FROM business_sources bs
            JOIN unnest(%s::text[], %s::text[]) AS q(source, source_record_id)
              ON bs.source = q.source AND bs.source_record_id = q.source_record_id
            """,
            (src_names, src_recs),
        )
        found_sources = await res.fetchall()
        src_map = {
            (r["source"] if isinstance(r, dict) else r[1], r["source_record_id"] if isinstance(r, dict) else r[2]):
            (r["business_id"] if isinstance(r, dict) else r[0])
            for r in found_sources
        }
        for idx, s_name, s_rec in source_pairs:
            if idx not in matched and (s_name, s_rec) in src_map:
                matched[idx] = src_map[(s_name, s_rec)]

    # 2. Website domain batch lookup for remaining
    domain_pairs = [(idx, e.website_domain) for idx, e in enumerate(entities) if idx not in matched and getattr(e, "website_domain", None)]
    if domain_pairs:
        domains = list({d for _, d in domain_pairs if d})
        res = await conn.execute(
            "SELECT id, website_domain FROM businesses WHERE website_domain = ANY(%s)",
            (domains,),
        )
        found_domains = await res.fetchall()
        dom_map = {
            (r["website_domain"] if isinstance(r, dict) else r[1]): (r["id"] if isinstance(r, dict) else r[0])
            for r in found_domains
        }
        for idx, d in domain_pairs:
            if idx not in matched and d in dom_map:
                matched[idx] = dom_map[d]

    # 3. Phone batch lookup for remaining
    phone_pairs = [(idx, e.phones_e164) for idx, e in enumerate(entities) if idx not in matched and getattr(e, "phones_e164", None)]
    if phone_pairs:
        all_phones = list({p for _, phones in phone_pairs for p in phones if p})
        if all_phones:
            res = await conn.execute(
                "SELECT id, phones_e164 FROM businesses WHERE phones_e164 && %s",
                (all_phones,),
            )
            found_phones = await res.fetchall()
            for r in found_phones:
                r_id = r["id"] if isinstance(r, dict) else r[0]
                r_phones = set(r["phones_e164"] if isinstance(r, dict) else r[1])
                for idx, phones in phone_pairs:
                    if idx not in matched and set(phones) & r_phones:
                        matched[idx] = r_id

    # 4. Spatial proximity + name check in a single batch lateral join query
    unmatched_spatial = [
        (idx, getattr(e, "lon"), getattr(e, "lat"))
        for idx, e in enumerate(entities)
        if idx not in matched and getattr(e, "lon", None) is not None and getattr(e, "lat", None) is not None
    ]
    if unmatched_spatial:
        s_idxs = [p[0] for p in unmatched_spatial]
        s_lons = [p[1] for p in unmatched_spatial]
        s_lats = [p[2] for p in unmatched_spatial]
        res = await conn.execute(
            """
            SELECT q.idx, b.id, b.canonical_name
            FROM unnest(%s::int[], %s::float8[], %s::float8[]) AS q(idx, lon, lat)
            CROSS JOIN LATERAL (
                SELECT id, canonical_name
                FROM businesses
                WHERE ST_DWithin(geom, ST_SetSRID(ST_MakePoint(q.lon, q.lat), 4326)::geography, 50)
                LIMIT 5
            ) b
            """,
            (s_idxs, s_lons, s_lats),
        )
        spatial_matches = await res.fetchall()
        for row in spatial_matches:
            s_idx = row["idx"] if isinstance(row, dict) else row[0]
            if s_idx in matched:
                continue
            b_id = row["id"] if isinstance(row, dict) else row[1]
            b_name = (row["canonical_name"] if isinstance(row, dict) else row[2] or "").lower()
            e = entities[s_idx]
            canon_name = (getattr(e, "canonical_name", "") or "").lower()
            name_norm = (getattr(e, "name_norm", "") or "").lower()
            if b_name and (b_name == canon_name or (name_norm and name_norm in b_name) or (canon_name and canon_name in b_name)):
                matched[s_idx] = b_id

    return matched


async def bulk_insert_rejected_candidates(
    conn: psycopg.AsyncConnection[Any],
    run_id: str,
    rejected_list: list[dict[str, Any]],
    batch_size: int = 500,
) -> int:
    """Insert rejected candidates in high-throughput batches."""
    if not rejected_list:
        return 0

    inserted = 0
    query = """
    INSERT INTO rejected_candidates (
        run_id, source, source_record_id, name, reason, reason_code, relevance_p, features
    ) VALUES (
        %s, %s, %s, %s, %s, %s, %s, %s
    )
    """

    for i in range(0, len(rejected_list), batch_size):
        batch = rejected_list[i : i + batch_size]
        params = [
            (
                run_id,
                r.get("source", "unknown"),
                r.get("source_record_id", ""),
                r.get("name", ""),
                r.get("reason", "Filtered by relevance rule"),
                r.get("reason_code", "veto"),
                r.get("relevance_p"),
                json.dumps(r.get("features", {})) if r.get("features") else None,
            )
            for r in batch
        ]
        async with conn.cursor() as cur:
            await cur.executemany(query, params)
        inserted += len(batch)

    return inserted


async def bulk_upsert_businesses(
    conn: psycopg.AsyncConnection[Any],
    businesses: list[dict[str, Any]],
    batch_size: int = 250,
) -> int:
    """Batch upsert businesses using lon-first coordinates and natural key deduplication."""
    if not businesses:
        return 0

    upsert_sql = """
    INSERT INTO businesses (
        id, canonical_name, name_norm, primary_category, categories,
        phones_e164, emails, website_url, website_domain, socials,
        address, address_text, locality, city, state, country,
        geom, geohash7, operating_status, confidence, tier,
        independent_source_count, first_seen_at, last_verified_at, updated_at
    ) VALUES (
        %(id)s, %(canonical_name)s, %(name_norm)s, %(primary_category)s, %(categories)s,
        %(phones_e164)s, %(emails)s, %(website_url)s, %(website_domain)s, %(socials)s,
        %(address)s, %(address_text)s, %(locality)s, %(city)s, %(state)s, %(country)s,
        ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)::geography, %(geohash7)s, %(operating_status)s, %(confidence)s, %(tier)s,
        %(independent_source_count)s, NOW(), NOW(), NOW()
    )
    ON CONFLICT (id) DO UPDATE SET
        canonical_name = EXCLUDED.canonical_name,
        name_norm = EXCLUDED.name_norm,
        primary_category = COALESCE(EXCLUDED.primary_category, businesses.primary_category),
        categories = EXCLUDED.categories,
        phones_e164 = EXCLUDED.phones_e164,
        emails = EXCLUDED.emails,
        website_url = COALESCE(EXCLUDED.website_url, businesses.website_url),
        website_domain = COALESCE(EXCLUDED.website_domain, businesses.website_domain),
        confidence = GREATEST(businesses.confidence, EXCLUDED.confidence),
        tier = CASE WHEN EXCLUDED.confidence >= businesses.confidence THEN EXCLUDED.tier ELSE businesses.tier END,
        independent_source_count = GREATEST(businesses.independent_source_count, EXCLUDED.independent_source_count),
        last_verified_at = NOW(),
        updated_at = NOW()
    """

    for i in range(0, len(businesses), batch_size):
        raw_batch = businesses[i : i + batch_size]
        batch = [
            {
                **b,
                "socials": b["socials"] if isinstance(b.get("socials"), Jsonb) else Jsonb(b.get("socials") or {}),
                "address": b["address"] if isinstance(b.get("address"), Jsonb) else Jsonb(b.get("address") or {}),
            }
            for b in raw_batch
        ]
        async with conn.cursor() as cur:
            await cur.executemany(upsert_sql, batch)

    return len(businesses)


async def bulk_insert_business_sources(
    conn: psycopg.AsyncConnection[Any],
    sources: list[dict[str, Any]],
    batch_size: int = 500,
) -> int:
    """Batch insert business sources."""
    if not sources:
        return 0

    query = """
    INSERT INTO business_sources (business_id, source, source_record_id, fetched_at)
    VALUES (%(business_id)s, %(source)s, %(source_record_id)s, NOW())
    ON CONFLICT (source, source_record_id) DO UPDATE SET
        business_id = EXCLUDED.business_id,
        fetched_at = NOW()
    """
    for i in range(0, len(sources), batch_size):
        batch = sources[i : i + batch_size]
        async with conn.cursor() as cur:
            await cur.executemany(query, batch)

    return len(sources)


async def bulk_insert_field_provenance(
    conn: psycopg.AsyncConnection[Any],
    provenance: list[dict[str, Any]],
    batch_size: int = 500,
) -> int:
    """Batch insert field provenance entries."""
    if not provenance:
        return 0

    query = """
    INSERT INTO field_provenance (
        business_id, field, value, source, evidence_url,
        evidence_quote, extracted_by, confidence, is_selected, observed_at
    ) VALUES (
        %(business_id)s, %(field)s, %(value)s, %(source)s, %(evidence_url)s,
        %(evidence_quote)s, %(extracted_by)s, %(confidence)s, %(is_selected)s, NOW()
    )
    """
    for i in range(0, len(provenance), batch_size):
        batch = provenance[i : i + batch_size]
        async with conn.cursor() as cur:
            await cur.executemany(query, batch)

    return len(provenance)


async def bulk_insert_verifications(
    conn: psycopg.AsyncConnection[Any],
    verifications: list[dict[str, Any]],
    batch_size: int = 500,
) -> int:
    """Batch insert or update verifications."""
    if not verifications:
        return 0

    query = """
    INSERT INTO verifications (business_id, check_name, outcome, detail, checked_at)
    VALUES (%(business_id)s, %(check_name)s, %(outcome)s, %(detail)s, %(checked_at)s)
    ON CONFLICT (business_id, check_name) DO UPDATE SET
        outcome = EXCLUDED.outcome,
        detail = EXCLUDED.detail,
        checked_at = EXCLUDED.checked_at
    """
    for i in range(0, len(verifications), batch_size):
        raw_batch = verifications[i : i + batch_size]
        batch = [
            {
                **v,
                "detail": v["detail"] if isinstance(v.get("detail"), Jsonb) else Jsonb(v.get("detail") or {}),
            }
            for v in raw_batch
        ]
        async with conn.cursor() as cur:
            await cur.executemany(query, batch)

    return len(verifications)


async def bulk_upsert_run_results(
    conn: psycopg.AsyncConnection[Any],
    results: list[dict[str, Any]],
    batch_size: int = 500,
) -> int:
    """Batch upsert run results."""
    if not results:
        return 0

    query = """
    INSERT INTO run_results (
        run_id, business_id, keyword, match_score, match_reason, rank, is_new_business, edge_case,
        decision, relevance_p, relevance_stage, relevance_features, relevance_reasons,
        concept_id, concept_version, scorer_version
    ) VALUES (
        %(run_id)s, %(business_id)s, %(keyword)s, %(match_score)s, %(match_reason)s, %(rank)s, %(is_new_business)s, %(edge_case)s,
        %(decision)s, %(relevance_p)s, %(relevance_stage)s, %(relevance_features)s, %(relevance_reasons)s,
        %(concept_id)s, %(concept_version)s, %(scorer_version)s
    )
    ON CONFLICT (run_id, business_id, keyword) DO UPDATE SET
        rank = EXCLUDED.rank,
        match_score = EXCLUDED.match_score,
        is_new_business = EXCLUDED.is_new_business,
        decision = EXCLUDED.decision,
        relevance_p = EXCLUDED.relevance_p,
        relevance_stage = EXCLUDED.relevance_stage,
        relevance_features = EXCLUDED.relevance_features,
        relevance_reasons = EXCLUDED.relevance_reasons,
        concept_id = EXCLUDED.concept_id,
        concept_version = EXCLUDED.concept_version,
        scorer_version = EXCLUDED.scorer_version
    """
    for i in range(0, len(results), batch_size):
        raw_batch = results[i : i + batch_size]
        batch = [
            {
                **r,
                "relevance_features": r["relevance_features"] if isinstance(r.get("relevance_features"), Jsonb) else Jsonb(r.get("relevance_features") or {}),
                "relevance_reasons": r["relevance_reasons"] if isinstance(r.get("relevance_reasons"), Jsonb) else Jsonb(r.get("relevance_reasons") or []),
            }
            for r in raw_batch
        ]
        async with conn.cursor() as cur:
            await cur.executemany(query, batch)

    return len(results)


