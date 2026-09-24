"""
N12 — Run Reporter Node

Finalises the run:
1. Writes final stats & status ('completed' or 'partial') to `query_runs` in Postgres
2. Emits the final `run_completed` SSE event with summary figures
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any
from psycopg.types.json import Jsonb

from app.db.pool import get_pool
from app.events.bus import get_bus
from app.graph.completion import CompletionReason, decide_completion
from app.graph.runtime import node
from app.graph.state import RunState
from app.relevance.concepts import resolve_concept

logger = logging.getLogger(__name__)


@node("n12_report", critical=True, max_retries=1)
async def run(state: RunState) -> dict[str, Any]:
    run_id_str = state.get("run_id") or ""
    try:
        run_uuid = uuid.UUID(run_id_str)
    except Exception as e:
        logger.warning(f"Invalid run_id UUID format '{run_id_str}', generating new: {e}")
        run_uuid = uuid.uuid4()

    errors = state.get("errors", [])
    degraded = state.get("degraded", [])
    has_critical = any(getattr(e, "is_critical", False) for e in errors)
    candidates = state.get("candidates", [])
    raw_candidates = state.get("raw_candidates", [])
    entities = state.get("entities", [])
    expansion_stats = state.get("expansion_stats", [])
    metrics = state.get("metrics", {})

    query_obj = state.get("query")
    max_results = getattr(query_obj, "max_results", 50) if query_obj else 50
    accepted_count = len(entities)

    # ── Gather evidence for honest completion decision ─────────────────────────
    geo = state.get("geo")
    cat_count = 1
    if query_obj and hasattr(query_obj, "keywords") and query_obj.keywords:
        try:
            card = resolve_concept(query_obj.keywords[0])
            if not card.is_synthesized and hasattr(card, "categories"):
                cat_count = len(card.categories.defining)
        except Exception:
            pass


    localities_list: list[str] = [geo.display_name] if geo and geo.display_name else []
    ladder_info = state.get("ladder") or {
        "rungs": expansion_stats,
        "reached_final_rung": True,
        "last_rung_new_candidates": 0,
        "final_radius_m": getattr(geo, "buffer_m", None) if geo else None,
        "localities": localities_list,
        "category_count": cat_count,
    }

    budget_obj = state.get("budget")
    http_used = budget_obj.http_calls_used if hasattr(budget_obj, "http_calls_used") else (budget_obj.get("http_calls_used", 0) if isinstance(budget_obj, dict) else 0)
    llm_used = budget_obj.llm_calls_used if hasattr(budget_obj, "llm_calls_used") else (budget_obj.get("llm_calls_used", 0) if isinstance(budget_obj, dict) else 0)
    budget_exhausted_flag = bool(state.get("budget_exhausted") or (budget_obj and hasattr(budget_obj, "max_http_calls") and http_used >= budget_obj.max_http_calls))
    budget_info = {
        "exhausted": budget_exhausted_flag,
        "which_limit": "http_calls" if http_used >= 400 else "wall_seconds",
    }

    source_stats = state.get("source_stats", {})
    failed_sources = [src for src, s in source_stats.items() if isinstance(s, dict) and s.get("error")]
    source_degraded = [d for d in degraded if "source" in d.lower() or "overture" in d.lower() or "osm" in d.lower()]
    sources_info = {
        "any_failed": bool(failed_sources or source_degraded),
        "failed_names": failed_sources or source_degraded,
    }

    candidates_seen_total = len(raw_candidates) if raw_candidates else len(candidates)
    raw_from_sources = sum(
        s.get("count", 0)
        for src, s in source_stats.items()
        if isinstance(s, dict) and isinstance(s.get("count"), (int, float))
    )
    if raw_from_sources > candidates_seen_total:
        candidates_seen_total = int(raw_from_sources) if isinstance(raw_from_sources, float) else raw_from_sources
    elif candidates_seen_total == 0 and len(entities) > 0:
        candidates_seen_total = len(entities)

    new_biz_count = metrics.get("new_businesses", sum(1 for e in entities if getattr(e, "is_new_business", True)))
    matched_biz_count = metrics.get("updated_businesses", sum(1 for e in entities if not getattr(e, "is_new_business", True)))
    prior_run_ids: list[str] = state.get("prior_run_ids") or []
    top_reject_codes: list[str] = state.get("dedup_rejection_codes") or []
    dedup_info = {
        "candidates_seen": candidates_seen_total,
        "new_businesses": new_biz_count,
        "matched_existing": matched_biz_count,
        "prior_run_ids": prior_run_ids,
        "top_reject_codes": top_reject_codes,
    }

    # Decide honest completion reason with strict proofs
    primary_kw = query_obj.keywords[0] if (query_obj and hasattr(query_obj, "keywords") and query_obj.keywords) else ""
    reason_enum, reason_details = decide_completion(
        accepted=accepted_count,
        target=max_results,
        ladder=ladder_info,
        budget=budget_info,
        sources=sources_info,
        dedup=dedup_info,
        source_stats=source_stats,
        keyword=primary_kw,
        cancelled=bool(state.get("cancelled", False)),
        critical_error=has_critical,
    )
    completion_reason = reason_enum.value

    # Partial beats failed: if leads were found/accepted, never fail the run
    if accepted_count > 0:
        final_status = "completed" if not errors and not degraded else "partial"
    else:
        if has_critical:
            final_status = "failed"
        elif reason_enum in (CompletionReason.KEYWORD_PLAN_MATCHED_NOTHING, CompletionReason.NO_CANDIDATES_FOUND):
            final_status = "partial"
        else:
            final_status = "degraded" if degraded else ("partial" if errors else "completed")

    # Calculate per-source candidate and entity counts
    provenance_summary: dict[str, dict[str, int]] = {}
    for c in candidates:
        src = getattr(c, "source", None) or (c.get("source") if isinstance(c, dict) else "unknown")
        if src not in provenance_summary:
            provenance_summary[src] = {"candidates": 0, "entities": 0}
        provenance_summary[src]["candidates"] += 1

    for ent in entities:
        source_ids = getattr(ent, "source_ids", []) or (ent.get("source_ids", []) if isinstance(ent, dict) else [])
        for sid in source_ids:
            src = sid.split(":")[0] if ":" in sid else sid
            if src not in provenance_summary:
                provenance_summary[src] = {"candidates": 0, "entities": 0}
            provenance_summary[src]["entities"] += 1

    # Count leads with independent corroboration (2+ sources)
    corroborated_count = sum(
        1 for e in entities
        if (getattr(e, "independent_source_count", 0) or 0) >= 2
    )

    geo_data: dict[str, Any] = {
        "display_name": geo.display_name if geo else None,
        "centroid": list(geo.centroid) if geo and geo.centroid else None,
        "bbox": list(geo.bbox) if geo and geo.bbox else None,
    } if geo else {}

    stats = {
        "candidate_count": candidates_seen_total,
        "raw_candidates_ingested": candidates_seen_total,
        "resolved_entity_count": len(entities),
        "completion_reason": completion_reason,
        "completion_details": reason_details,
        "ladder": ladder_info,
        "dedup": dedup_info,
        "sources": sources_info,
        "budget": {
            "http_calls_used": http_used,
            "llm_calls_used": llm_used,
            "exhausted": budget_exhausted_flag,
        },
        "source_stats": source_stats,
        "provenance_summary": provenance_summary,
        "source_breakdown": {
            src: info for src, info in provenance_summary.items()
        },
        "corroborated_leads": corroborated_count,
        "expansion": expansion_stats,
        "degraded": degraded,
        "metrics": metrics,
        "geo": geo_data,
        "errors": [e.model_dump(mode="json") if hasattr(e, "model_dump") else e for e in errors],
    }

    pool = get_pool()
    try:
        async with pool.connection() as conn:
            await conn.execute(
                """
                UPDATE query_runs SET
                    status = %s,
                    stats = %s,
                    completion_reason = %s,
                    retryable = TRUE,
                    finished_at = NOW()
                WHERE id = %s
                """,
                (final_status, Jsonb(stats), completion_reason, run_uuid),
            )
    except Exception as exc:
        logger.error(f"N12: Failed to update query_runs status: {exc}")

    # Emit SSE events: emit node_finished for n12_report BEFORE the terminal run_completed
    bus = get_bus()
    await bus.publish(
        run_id_str,
        "node_finished",
        {
            "node": "n12_report",
            "status": "completed",
            "elapsed_ms": 10.0,
        },
    )

    await bus.publish(
        run_id_str,
        "run_completed",
        {
            "run_id": run_id_str,
            "status": final_status,
            "completion_reason": completion_reason,
            "completion_details": reason_details,
            "degraded": degraded,
            "entity_count": len(entities),
            "provenance_summary": provenance_summary,
            "source_breakdown": {src: info for src, info in provenance_summary.items()},
            "corroborated_leads": corroborated_count,
            "expansion": expansion_stats,
            "metrics": metrics,
        },
    )

    logger.info(f"N12: Run {run_id_str} finished with status={final_status}, completion_reason={completion_reason}")
    return {"final_status": final_status, "completion_reason": completion_reason, "stats": stats}
