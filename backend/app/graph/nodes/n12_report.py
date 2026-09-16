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

from app.db.pool import get_pool
from app.events.bus import get_bus
from app.graph.runtime import node
from app.graph.state import RunState

logger = logging.getLogger(__name__)


@node("n12_report", critical=True, max_retries=1)
async def run(state: RunState) -> dict[str, Any]:
    run_id_str = state["run_id"]
    try:
        run_uuid = uuid.UUID(run_id_str)
    except Exception:
        run_uuid = uuid.uuid4()

    errors = state.get("errors", [])
    has_critical = any(e.is_critical for e in errors)
    final_status = "failed" if has_critical else ("partial" if errors else "completed")

    budget_obj = state.get("budget")
    http_used = budget_obj.http_calls_used if hasattr(budget_obj, "http_calls_used") else (budget_obj.get("http_calls_used", 0) if isinstance(budget_obj, dict) else 0)
    llm_used = budget_obj.llm_calls_used if hasattr(budget_obj, "llm_calls_used") else (budget_obj.get("llm_calls_used", 0) if isinstance(budget_obj, dict) else 0)

    geo = state.get("geo")
    stats = {
        "candidate_count": len(state.get("candidates", [])),
        "resolved_entity_count": len(state.get("entities", [])),
        "source_stats": state.get("source_stats", {}),
        "metrics": state.get("metrics", {}),
        "geo": {
            "display_name": geo.display_name if geo else None,
            "centroid": list(geo.centroid) if geo and geo.centroid else None,
            "bbox": list(geo.bbox) if geo and geo.bbox else None,
        } if geo else {},
        "budget": {
            "http_calls_used": http_used,
            "llm_calls_used": llm_used,
        },
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
                    finished_at = NOW()
                WHERE id = %s
                """,
                (final_status, json.dumps(stats), run_uuid),
            )
    except Exception as exc:
        logger.error(f"N12: Failed to update query_runs status: {exc}")

    # Emit SSE final event
    bus = get_bus()
    await bus.publish(
        run_id_str,
        "run_completed",
        {
            "run_id": run_id_str,
            "status": final_status,
            "entity_count": len(state.get("entities", [])),
            "metrics": state.get("metrics", {}),
        },
    )

    logger.info(f"N12: Run {run_id_str} finished with status={final_status}")
    return {"final_status": final_status, "stats": stats}
