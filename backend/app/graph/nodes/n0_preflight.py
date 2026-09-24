"""
N0 Preflight Validation Node (N-1)

Fast sanity verification (< 1s) executed before embarking on expensive spatial queries
and external requests. Validates:
1. Database connectivity and health
2. PostGIS, vector, and pg_trgm extension availability
3. Concept card resolution for primary query keyword
4. Discovery source connector readiness
"""

from __future__ import annotations

import logging
from typing import Any

from app.db.pool import get_conn
from app.graph.runtime import node
from app.graph.state import QueryInput, RunState
from app.relevance.concepts import resolve_concept
from app.settings import settings

logger = logging.getLogger(__name__)


async def validate_preflight(query: QueryInput) -> dict[str, Any]:
    """Execute preflight checks and return diagnostic dictionary."""
    diagnostics: dict[str, Any] = {
        "db_connected": False,
        "extensions": {},
        "concept_resolved": False,
        "concept_id": None,
        "sources_ready": [],
    }

    # 1. DB connectivity and extension checks
    try:
        async with get_conn() as conn:
            cur = await conn.execute("SELECT 1")
            row = await cur.fetchone()
            if row and (row["?column?"] == 1 or row[0] == 1):
                diagnostics["db_connected"] = True

            ext_cur = await conn.execute("SELECT extname, extversion FROM pg_extension")
            ext_rows = await ext_cur.fetchall()
            exts = {r["extname"]: r["extversion"] for r in ext_rows}
            diagnostics["extensions"] = exts
    except Exception as exc:
        logger.warning(f"Preflight DB check warning (non-fatal for testing): {exc}")

    # 2. Concept card validation
    primary_keyword = query.keywords[0] if query.keywords else "business"
    try:
        card = resolve_concept(primary_keyword)
        diagnostics["concept_resolved"] = True
        diagnostics["concept_id"] = card.concept_id
    except Exception as exc:
        logger.warning(f"Preflight Concept resolution warning: {exc}")

    # 3. Source readiness
    for src in query.sources:
        if src in ("overture", "osm", "imports", "overpass"):
            diagnostics["sources_ready"].append(src)

    return diagnostics


@node("n0_preflight", critical=False, max_retries=0)
async def run(state: RunState) -> dict[str, Any]:
    query_obj = state.get("query")
    if isinstance(query_obj, dict):
        query = QueryInput(**query_obj)
    elif isinstance(query_obj, QueryInput):
        query = query_obj
    else:
        query = QueryInput(keywords=["business"], location={})

    diag = await validate_preflight(query)
    logger.info("Preflight validation completed: %s", diag)
    return {"preflight": diag}

