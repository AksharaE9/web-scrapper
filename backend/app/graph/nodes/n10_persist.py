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
from psycopg.types.json import Jsonb

from app.db.bulk import (
    bulk_insert_business_sources,
    bulk_insert_field_provenance,
    bulk_insert_verifications,
    bulk_match_existing_businesses,
    bulk_upsert_businesses,
    bulk_upsert_run_results,
)
from app.db.pool import get_pool
from app.graph.runtime import node
from app.graph.state import ResolvedEntity, RunState

logger = logging.getLogger(__name__)


@node("n10_persist", critical=False, max_retries=1, timeout_seconds=180.0)
async def run(state: RunState) -> dict[str, Any]:
    run_id_str = state["run_id"]

    entities: list[ResolvedEntity] = state.get("entities", [])
    if not entities:
        logger.info(f"N10: No entities to persist for run {run_id_str}")
        return {"entities": []}

    query_obj = state.get("query")
    max_results = getattr(query_obj, "max_results", 50) if query_obj else 50
    raw_entity_count = len(entities)
    target_entities = entities[:max_results] if max_results else entities
    logger.info(
        f"N10 Funnel Telemetry: [Stage 1: Relevance Accepted = {raw_entity_count}] -> "
        f"[Stage 2: Target Slicing (top_k={max_results}) = {len(target_entities)}]"
    )

    pool = get_pool()
    updated_entities: list[ResolvedEntity] = []
    new_count = 0
    updated_count = 0

    async with pool.connection() as conn:
        async with conn.transaction():
            # 1. High-throughput bulk matching against existing database records
            matched_map = await bulk_match_existing_businesses(conn, target_entities)

            businesses_to_upsert: list[dict[str, Any]] = []
            sources_to_insert: list[dict[str, Any]] = []
            provenance_to_insert: list[dict[str, Any]] = []
            verifications_to_insert: list[dict[str, Any]] = []
            results_to_upsert: list[dict[str, Any]] = []

            kw = state["query"].keywords[0] if (state.get("query") and state["query"].keywords) else "lead"

            for rank, entity in enumerate(target_entities, start=1):
                if not entity.id:
                    entity.id = str(uuid.uuid4())

                matched_id = matched_map.get(rank - 1)
                is_new = matched_id is None
                target_id = str(matched_id) if matched_id else entity.id

                if is_new:
                    new_count += 1
                    entity.is_new_business = True
                else:
                    updated_count += 1
                    entity.is_new_business = False
                    entity.id = target_id

                businesses_to_upsert.append({
                    "id": target_id,
                    "canonical_name": entity.canonical_name,
                    "name_norm": entity.name_norm,
                    "primary_category": entity.primary_category,
                    "categories": entity.categories,
                    "phones_e164": entity.phones_e164,
                    "emails": entity.emails,
                    "website_url": entity.website_url,
                    "website_domain": entity.website_domain,
                    "socials": Jsonb(entity.socials or {}),
                    "address": Jsonb(entity.address or {}),
                    "address_text": entity.address_text,
                    "locality": entity.locality,
                    "city": entity.city,
                    "state": entity.state,
                    "country": entity.country,
                    "lon": entity.lon,
                    "lat": entity.lat,
                    "geohash7": entity.geohash7,
                    "operating_status": entity.operating_status,
                    "confidence": entity.confidence,
                    "tier": entity.tier,
                    "independent_source_count": entity.independent_source_count,
                    "run_id": run_id_str,
                })

                # Business sources
                for src_id_str in entity.source_ids:
                    if ":" in src_id_str:
                        src_name, src_rec_id = src_id_str.split(":", 1)
                        sources_to_insert.append({
                            "business_id": target_id,
                            "source": src_name,
                            "source_record_id": src_rec_id,
                        })

                # Field provenance
                for prov in entity.field_provenance:
                    provenance_to_insert.append({
                        "business_id": target_id,
                        "field": prov.field,
                        "value": prov.value,
                        "source": prov.source,
                        "evidence_url": prov.evidence_url,
                        "evidence_quote": prov.evidence_quote,
                        "extracted_by": prov.extracted_by,
                        "confidence": prov.confidence,
                        "is_selected": prov.is_selected,
                    })

                # Verifications
                for chk in entity.checks:
                    verifications_to_insert.append({
                        "business_id": target_id,
                        "check_name": chk.check_name,
                        "outcome": chk.outcome,
                        "detail": Jsonb(chk.detail or {}),
                        "checked_at": chk.checked_at,
                    })

                # Run results
                dec = entity.relevance_decision or {}
                results_to_upsert.append({
                    "run_id": run_id_str,
                    "business_id": target_id,
                    "keyword": kw,
                    "match_score": entity.confidence,
                    "match_reason": f"Rank #{rank} by confidence ({entity.tier})",
                    "rank": rank,
                    "is_new_business": entity.is_new_business,
                    "edge_case": entity.edge_case,
                    "decision": dec.get("decision", "accepted"),
                    "relevance_p": dec.get("relevance_p", entity.confidence),
                    "relevance_stage": dec.get("relevance_stage", "cascade"),
                    "relevance_features": Jsonb(dec.get("relevance_features", {})),
                    "relevance_reasons": Jsonb(dec.get("relevance_reasons", [])),
                    "concept_id": dec.get("concept_id"),
                    "concept_version": dec.get("concept_version", 1),
                    "scorer_version": dec.get("scorer_version", "v2.2"),
                })

                updated_entities.append(entity)

            # Execute batch operations
            if businesses_to_upsert:
                await bulk_upsert_businesses(conn, businesses_to_upsert)
            if sources_to_insert:
                await bulk_insert_business_sources(conn, sources_to_insert)
            if provenance_to_insert:
                await bulk_insert_field_provenance(conn, provenance_to_insert)
            if verifications_to_insert:
                await bulk_insert_verifications(conn, verifications_to_insert)
            if results_to_upsert:
                await bulk_upsert_run_results(conn, results_to_upsert)

    logger.info(
        f"N10: Bulk persisted {len(updated_entities)} entities ({new_count} new, {updated_count} updated) for run {run_id_str}"
    )

    return {
        "entities": updated_entities,
        "metrics": {
            "persisted_count": len(updated_entities),
            "new_businesses": new_count,
            "updated_businesses": updated_count,
        },
    }

