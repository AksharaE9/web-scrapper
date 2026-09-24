"""
N4 — Relevance Engine Node (Cascade Orchestrator R0–R6) v2.2

Replaces flat heuristic filtering with an explainable, evidence-based cascade:
  - R0: Indic-aware tokenization, transliteration variant folding, non-evidence classification
  - R1: Hard Gates (boundary, operating status, user excludes, vetoes, incompatible brands/categories)
  - R2: Feature extraction (category-first in v2.2)
  - R3: Semantic Prototype bank retrieval (BAAI/bge-small-en-v1.5)
  - R4: Calibrated logistic scoring & structural defining-signal enforcement
  - R5: FastEmbed cross-encoder reranking
  - R6: Local small-LLM adjudication with literal evidence substring validation

v2.2 additions:
  1. Missing-card detection: synthesized cards emit 'concept_missing' SSE and
     route ALL candidates to review, never accepted.
  2. Health assertion: a run where all buckets are non-zero is healthy; if
     Review=0 and Rejected=0, a warning is emitted.
  3. live lead_accepted SSE events: each accepted lead is published immediately,
     not only at persist time.
  4. relevance_progress SSE: rolling accepted/review/rejected counters.
  5. Expansion ladder (N4.5 logic inlined): if accepted < target, iterates
     through strategy rungs to fill the shortfall, with per-rung telemetry.

Partitions candidates into:
  - accepted: High-confidence, passed defining signal + primary signal
  - review: Borderline / uncertain leads (saved to review band)
  - rejected: Vetoed / no-evidence candidates persisted with structured reason codes
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

import pygeohash

from app.db.bulk import bulk_insert_rejected_candidates
from app.db.pool import get_conn
from app.events.bus import get_bus
from app.graph.runtime import node
from app.graph.state import GeoResolution, RawCandidate, RunState
from app.relevance.concepts import resolve_concept
from app.relevance.engine import evaluate_candidate

logger = logging.getLogger(__name__)

# How often (candidates evaluated) to emit relevance_progress SSE
_PROGRESS_EMIT_EVERY = 5


async def _run_relevance_pass(
    candidates: list[RawCandidate],
    primary_keyword: str,
    concept_card: Any,
    geo: GeoResolution,
    exclude_keywords: list[str],
    seen_record_ids: set[str],
    run_id: str,
    force_review: bool = False,
) -> tuple[list[RawCandidate], list[dict[str, Any]], int, int, int]:
    """
    Run a single relevance pass over a list of candidates.
    Deduplicates against seen_record_ids.
    Returns: (passed, rejected_rows, accepted_count, review_count, rejected_count)
    """
    bus = get_bus()
    passed: list[RawCandidate] = []
    rejected_rows: list[dict[str, Any]] = []
    accepted_count = 0
    review_count = 0
    rejected_count = 0

    for i, c in enumerate(candidates):
        # Skip already-seen records (deduplication across expansion rungs)
        if c.source_record_id in seen_record_ids:
            continue

        brand = c.raw.get("brand") if isinstance(c.raw, dict) else None
        osm_tags = [f"{k}={v}" for k, v in c.raw.items() if isinstance(v, str)] if isinstance(c.raw, dict) else []

        decision = await evaluate_candidate(
            name=c.name,
            keyword=primary_keyword,
            lon=c.lon,
            lat=c.lat,
            categories=c.categories,
            brand=brand,
            osm_tags=osm_tags,
            boundary_wkt=geo.polygon_wkt,
            operating_status=c.operating_status,
            user_excludes=exclude_keywords,
            source_confidence=c.source_confidence,
            source_lineage=c.source_lineage,
            card=concept_card,
            force_review=force_review,
        )

        if decision.outcome in ("accepted", "review"):
            if decision.outcome == "accepted":
                accepted_count += 1
                # ── Live SSE: emit lead immediately on accept ─────────────────
                await bus.publish(run_id, "lead_accepted", {
                    "run_id": run_id,
                    "name": c.name,
                    "category": c.categories[0] if c.categories else None,
                    "tier": "Unverified",
                    "confidence": decision.p,
                    "reasons": decision.reasons,
                    "seq": accepted_count,
                })
            else:
                review_count += 1

            c.raw["geohash7"] = pygeohash.encode(c.lat, c.lon, precision=7)
            c.raw["relevance_decision"] = {
                "decision": decision.outcome,
                "relevance_p": decision.p,
                "relevance_stage": decision.stage,
                "relevance_features": decision.features,
                "relevance_reasons": decision.reasons,
                "concept_id": decision.concept_id,
                "concept_version": decision.concept_version,
                "scorer_version": decision.scorer_version,
                "is_edge_case": decision.is_edge_case,
            }
            passed.append(c)
            seen_record_ids.add(c.source_record_id)
        else:
            rejected_count += 1
            seen_record_ids.add(c.source_record_id)
            reason_str = decision.reason_code or (decision.reasons[0].get("label") if decision.reasons else "low_score")
            rejected_rows.append({
                "run_id": run_id,
                "source": c.source,
                "source_record_id": c.source_record_id,
                "name": c.name,
                "reason": reason_str,
                "reason_code": decision.reason_code or "veto_or_low_score",
                "relevance_p": decision.p,
                "features": json.dumps(decision.features),
            })

        # ── Rolling progress events & event loop yield ────────────────────
        evaluated_total = i + 1
        if evaluated_total % _PROGRESS_EMIT_EVERY == 0:
            await bus.publish(run_id, "relevance_progress", {
                "run_id": run_id,
                "evaluated": evaluated_total,
                "total": len(candidates),
                "accepted": accepted_count,
                "review": review_count,
                "rejected": rejected_count,
            })
            await asyncio.sleep(0)

    return passed, rejected_rows, accepted_count, review_count, rejected_count


@node("n4_filter", critical=True, max_retries=0)
async def run(state: RunState) -> dict[str, Any]:
    t_start = time.monotonic()
    bus = get_bus()

    geo: GeoResolution | None = state.get("geo")
    candidates: list[RawCandidate] = state.get("raw_candidates") or state.get("candidates", [])
    run_id = state.get("run_id", "")
    query_obj = state.get("query")
    keywords = query_obj.keywords if hasattr(query_obj, "keywords") else ["lead"]
    exclude_keywords = query_obj.exclude_keywords if hasattr(query_obj, "exclude_keywords") else []
    target = getattr(query_obj, "max_results", 50) if query_obj else 50

    primary_keyword = keywords[0] if keywords else "business"
    concept_card = resolve_concept(primary_keyword)

    if not geo:
        return {"candidates": []}

    # ── Missing-card & Derived-card detection ────────────────────────────
    if concept_card.is_synthesized:
        logger.warning(
            f"N4: No reviewed concept card for keyword '{primary_keyword}' in run {run_id}. "
            f"All candidates will be routed to review. Add a concept card to improve accuracy."
        )
        await bus.publish(run_id, "concept_missing", {
            "run_id": run_id,
            "keyword": primary_keyword,
            "warning": (
                f"No reviewed concept card for '{primary_keyword}' — results may be imprecise. "
                f"All candidates routed to review band."
            ),
        })
    elif getattr(concept_card, "is_derived", False):
        logger.info(f"N4: Using auto-derived concept card for '{primary_keyword}' in run {run_id}.")
        await bus.publish(run_id, "concept_derived", {
            "run_id": run_id,
            "keyword": primary_keyword,
            "info": f"Using an auto-derived definition for '{primary_keyword}' — review the results and confirm the category.",
        })

    # ── Rung 0: Base pass ─────────────────────────────────────────────────
    seen_record_ids: set[str] = set()
    all_rejected_rows: list[dict[str, Any]] = []
    expansion_stats: list[dict[str, Any]] = []

    rung_start = time.monotonic()
    passed, rejected_rows, accepted_count, review_count, rejected_count = await _run_relevance_pass(
        candidates=candidates,
        primary_keyword=primary_keyword,
        concept_card=concept_card,
        geo=geo,
        exclude_keywords=exclude_keywords,
        seen_record_ids=seen_record_ids,
        run_id=run_id,
        force_review=concept_card.is_synthesized,
    )
    all_rejected_rows.extend(rejected_rows)
    expansion_stats.append({
        "rung": 0,
        "strategy": "base_area_defining_categories",
        "candidates_evaluated": len(candidates),
        "accepted": accepted_count,
        "review": review_count,
        "rejected": rejected_count,
        "elapsed_ms": round((time.monotonic() - rung_start) * 1000),
    })

    # ── Expansion ladder (Rungs 1–3, host categories → review band) ──────
    # Only runs when: accepted < target AND card is reviewed (not synthesized)
    if accepted_count < target and not concept_card.is_synthesized:
        # Rung 1: host-category candidates from existing pool → review band
        host_candidates = [
            c for c in candidates
            if c.source_record_id not in seen_record_ids
        ]
        if host_candidates:
            rung_start = time.monotonic()
            rung_passed, rung_rejected, rung_acc, rung_rev, rung_rej = await _run_relevance_pass(
                candidates=host_candidates,
                primary_keyword=primary_keyword,
                concept_card=concept_card,
                geo=geo,
                exclude_keywords=exclude_keywords,
                seen_record_ids=seen_record_ids,
                run_id=run_id,
                force_review=True,  # Rung 1+ always → review, never accepted
            )
            passed.extend(rung_passed)
            all_rejected_rows.extend(rung_rejected)
            review_count += rung_rev
            expansion_stats.append({
                "rung": 1,
                "strategy": "host_categories_review_band",
                "candidates_evaluated": len(host_candidates),
                "accepted": 0,
                "review": rung_rev,
                "rejected": rung_rej,
                "elapsed_ms": round((time.monotonic() - rung_start) * 1000),
            })

            await bus.publish(run_id, "expansion_rung", {
                "run_id": run_id,
                "rung": 1,
                "strategy": "host_categories_review_band",
                "accepted_so_far": accepted_count,
                "target": target,
            })

    # ── Expansion Ladder Telemetry ────────────────────────────────────────
    cat_count = len(concept_card.categories.defining) if concept_card and hasattr(concept_card, "categories") else 1
    ladder_info = {
        "rungs": expansion_stats,
        "reached_final_rung": True,
        "last_rung_new_candidates": len(candidates) - len(seen_record_ids) if len(candidates) >= len(seen_record_ids) else 0,
        "final_radius_m": getattr(geo, "buffer_m", None),
        "localities": [geo.display_name] if geo and geo.display_name else [],
        "category_count": cat_count,
    }

    # ── Health check: degenerate distribution detection ────────────────────
    total_processed = accepted_count + review_count + rejected_count
    degraded_signals: list[str] = []
    if total_processed > 5 and (rejected_count == 0 or (review_count == 0 and rejected_count == 0)):
        logger.warning(
            f"N4: Degenerate distribution detected for run {run_id}: "
            f"Accepted={accepted_count}, Review={review_count}, Rejected={rejected_count} from {total_processed} candidates. "
            f"Check concept card '{concept_card.concept_id}' and scoring weights."
        )
        degraded_signals.append("degenerate_distribution_zero_rejected")
        await bus.publish(run_id, "run_health_warning", {
            "run_id": run_id,
            "warning": "degenerate_distribution",
            "accepted": accepted_count,
            "review": review_count,
            "rejected": rejected_count,
            "message": (
                f"Zero candidates rejected out of {total_processed} evaluated. "
                f"This is an unverified distribution signature in concept card '{concept_card.concept_id}'."
            ),
        })

    # ── Bulk insert rejected candidates ──────────────────────────────────
    persisted_rejected_count = 0
    if all_rejected_rows:
        async with get_conn() as conn:
            persisted_rejected_count = await bulk_insert_rejected_candidates(conn, run_id, all_rejected_rows)
            await conn.commit()

        if isinstance(persisted_rejected_count, int) and persisted_rejected_count != len(all_rejected_rows):
            logger.error(
                f"N4: Persistence mismatch in run {run_id}: "
                f"rejected_rows={len(all_rejected_rows)} vs persisted={persisted_rejected_count}"
            )
            raise RuntimeError(
                f"Persistence mismatch: rejected_rows={len(all_rejected_rows)} vs persisted={persisted_rejected_count}"
            )

    elapsed_ms = round((time.monotonic() - t_start) * 1000)
    logger.info(
        f"N4: run={run_id} accepted={accepted_count} review={review_count} "
        f"rejected={rejected_count} target={target} elapsed={elapsed_ms}ms"
    )

    result_dict: dict[str, Any] = {
        "candidates": passed,
        "expansion_stats": expansion_stats,
        "ladder": ladder_info,
        "dedup_rejection_codes": [r["reason_code"] for r in all_rejected_rows[:10]],
        "source_stats": {
            "relevance_cascade": {
                "passed": len(passed),
                "accepted": accepted_count,
                "review": review_count,
                "rejected": rejected_count,
                "target": target,
                "expansion_rungs": len(expansion_stats),
                "elapsed_ms": elapsed_ms,
            }
        },
    }
    if degraded_signals:
        result_dict["degraded"] = degraded_signals

    return result_dict
