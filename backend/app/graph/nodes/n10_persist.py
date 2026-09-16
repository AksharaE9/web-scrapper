"""
N10 — GlobalDedup & Persister Agent

Persists resolved entities into Neon Postgres:
1. Global Deduplication:
   - Check if entity already exists in `businesses` table:
     - Exact match on (source, source_record_id) via `business_sources`
     - Exact phone / domain match
     - High spatial proximity (geom < 50m) + rapidfuzz name similarity > 85%
2. If business exists:
   - Merge new sources into `business_sources`
   - Merge new provenance entries into `field_provenance`
   - Update `businesses` record with better fields (higher confidence)
   - Mark `is_new_business = False`
3. If new business:
   - Insert new row into `businesses` with ST_SetSRID(ST_MakePoint(lon, lat), 4326)
   - Insert sources into `business_sources`
   - Insert provenance records
   - Mark `is_new_business = True`
4. Record relationship in `run_results` for this run_id with rank and match score
5. Record verifications in `verifications` table
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from app.db.pool import get_pool
from app.graph.runtime import node
from app.graph.state import ResolvedEntity, RunState

logger = logging.getLogger(__name__)


@node("n10_persist", critical=True, max_retries=2)
async def run(state: RunState) -> dict[str, Any]:
    run_id_str = str(state["run_id"])

    entities: list[ResolvedEntity] = state.get("entities", [])
    if not entities:
        logger.info(f"N10: No entities to persist for run {run_id_str}")
        return {"entities": []}

    pool = get_pool()
    updated_entities: list[ResolvedEntity] = []
    new_count = 0
    updated_count = 0

    async with pool.connection() as conn:
        async with conn.transaction():
            for rank, entity in enumerate(entities, start=1):
                if not entity.id:
                    entity.id = str(uuid.uuid4())
                ent_id = str(entity.id)

                # 1. Check existing business by phone or domain or sources
                matched_id: uuid.UUID | None = None

                # Check by source IDs
                for src_id_str in entity.source_ids:
                    if ":" in src_id_str:
                        src_name, src_rec_id = src_id_str.split(":", 1)
                        row = await conn.execute(
                            """
                            SELECT business_id FROM business_sources 
                            WHERE source = %s AND source_record_id = %s LIMIT 1
                            """,
                            (src_name, src_rec_id),
                        )
                        res = await row.fetchone()
                        if res:
                            matched_id = res["business_id"] if isinstance(res, dict) else res[0]
                            break

                # Check by domain
                if not matched_id and entity.website_domain:
                    row = await conn.execute(
                        "SELECT id FROM businesses WHERE website_domain = %s LIMIT 1",
                        (entity.website_domain,),
                    )
                    res = await row.fetchone()
                    if res:
                        matched_id = res["id"] if isinstance(res, dict) else res[0]

                # Check by phone
                if not matched_id and entity.phones_e164:
                    row = await conn.execute(
                        "SELECT id FROM businesses WHERE phones_e164 && %s LIMIT 1",
                        (entity.phones_e164,),
                    )
                    res = await row.fetchone()
                    if res:
                        matched_id = res["id"] if isinstance(res, dict) else res[0]

                # Check spatial proximity + name
                if not matched_id:
                    row = await conn.execute(
                        """
                        SELECT id, canonical_name 
                        FROM businesses 
                        WHERE ST_DWithin(geom, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, 50)
                        LIMIT 5
                        """,
                        (entity.lon, entity.lat),
                    )
                    neighbors = await row.fetchall()
                    for n in neighbors:
                        n_id = n["id"] if isinstance(n, dict) else n[0]
                        n_name = n["canonical_name"] if isinstance(n, dict) else n[1]
                        if n_name and (n_name.lower() == entity.canonical_name.lower() or 
                                       entity.name_norm in n_name.lower() or n_name.lower() in entity.name_norm):
                            matched_id = n_id
                            break

                is_new = matched_id is None
                target_id = matched_id or ent_id

                if is_new:
                    new_count += 1
                    entity.is_new_business = True
                    await conn.execute(
                        """
                        INSERT INTO businesses (
                            id, canonical_name, name_norm, primary_category, categories,
                            phones_e164, emails, website_domain, website_url, socials,
                            address, address_text, locality, city, state, country,
                            geohash7, operating_status, confidence, tier,
                            independent_source_count, geom, lon, lat, first_seen_at, last_verified_at, updated_at
                        ) VALUES (
                            %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s,
                            %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s, NOW(), NOW(), NOW()
                        )
                        ON CONFLICT (id) DO UPDATE SET
                            canonical_name = EXCLUDED.canonical_name,
                            lon = EXCLUDED.lon,
                            lat = EXCLUDED.lat,
                            confidence = GREATEST(businesses.confidence, EXCLUDED.confidence),
                            updated_at = NOW()
                        """,
                        (
                            target_id,
                            entity.canonical_name,
                            entity.name_norm,
                            entity.primary_category,
                            entity.categories,
                            entity.phones_e164,
                            entity.emails,
                            entity.website_domain,
                            entity.website_url,
                            json.dumps(entity.socials),
                            json.dumps(entity.address),
                            entity.address_text,
                            entity.locality,
                            entity.city,
                            entity.state,
                            entity.country,
                            entity.geohash7,
                            entity.operating_status,
                            entity.confidence,
                            entity.tier,
                            entity.independent_source_count,
                            entity.lon,
                            entity.lat,
                            entity.lon,
                            entity.lat,
                        ),
                    )
                else:
                    updated_count += 1
                    entity.is_new_business = False
                    entity.id = str(target_id)
                    await conn.execute(
                        """
                        UPDATE businesses SET
                            confidence = GREATEST(confidence, %s),
                            independent_source_count = GREATEST(independent_source_count, %s),
                            tier = CASE WHEN %s > confidence THEN %s ELSE tier END,
                            last_verified_at = NOW(),
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (
                            entity.confidence,
                            entity.independent_source_count,
                            entity.confidence,
                            entity.tier,
                            target_id,
                        ),
                    )

                # 2. Insert business_sources
                for src_id_str in entity.source_ids:
                    if ":" in src_id_str:
                        src_name, src_rec_id = src_id_str.split(":", 1)
                        await conn.execute(
                            """
                            INSERT INTO business_sources (business_id, source, source_record_id, fetched_at)
                            VALUES (%s, %s, %s, NOW())
                            ON CONFLICT (source, source_record_id) DO UPDATE SET
                                business_id = EXCLUDED.business_id,
                                fetched_at = NOW()
                            """,
                            (target_id, src_name, src_rec_id),
                        )

                # 3. Insert field_provenance
                for prov in entity.field_provenance:
                    await conn.execute(
                        """
                        INSERT INTO field_provenance (
                            business_id, field, value, source, evidence_url,
                            evidence_quote, extracted_by, confidence, is_selected, observed_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                        """,
                        (
                            target_id,
                            prov.field,
                            prov.value,
                            prov.source,
                            prov.evidence_url,
                            prov.evidence_quote,
                            prov.extracted_by,
                            prov.confidence,
                            prov.is_selected,
                        ),
                    )

                # 4. Insert verifications
                for chk in entity.checks:
                    await conn.execute(
                        """
                        INSERT INTO verifications (business_id, check_name, outcome, detail, checked_at)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (business_id, check_name) DO UPDATE SET
                            outcome = EXCLUDED.outcome,
                            detail = EXCLUDED.detail,
                            checked_at = EXCLUDED.checked_at
                        """,
                        (
                            target_id,
                            chk.check_name,
                            chk.outcome,
                            json.dumps(chk.detail),
                            chk.checked_at,
                        ),
                    )

                # 5. Insert run_results
                kw = state["query"].keywords[0] if state["query"].keywords else "lead"
                await conn.execute(
                    """
                    INSERT INTO run_results (
                        run_id, business_id, keyword, match_score, match_reason, rank, is_new_business, edge_case
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (run_id, business_id, keyword) DO UPDATE SET
                        rank = EXCLUDED.rank,
                        match_score = EXCLUDED.match_score,
                        is_new_business = EXCLUDED.is_new_business
                    """,
                    (
                        run_id_str,
                        str(target_id),
                        kw,
                        entity.confidence,
                        f"Rank #{rank} by confidence ({entity.tier})",
                        rank,
                        entity.is_new_business,
                        entity.edge_case,
                    ),
                )

                updated_entities.append(entity)

    logger.info(
        f"N10: Persisted {len(updated_entities)} entities ({new_count} new, {updated_count} updated) for run {run_id_str}"
    )

    return {
        "entities": updated_entities,
        "metrics": {
            "persisted_count": len(updated_entities),
            "new_businesses": new_count,
            "updated_businesses": updated_count,
        },
    }
