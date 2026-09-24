"""
Runs API router — POST /api/runs, GET /api/runs, GET /api/runs/{id}, SSE, cancel, rerun.
"""

from __future__ import annotations

import asyncio
import json
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncIterator

import structlog
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from psycopg import sql
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from app.db.pool import get_conn
from app.events.bus import HEARTBEAT_INTERVAL, SSEEvent, get_bus
from app.graph.build import get_compiled_graph
from app.settings import settings
from app.worker import RunWorker

log = structlog.get_logger()
router = APIRouter(tags=["runs"])


# ── Request / Response models ──────────────────────────────────────────────────

class LocationInput(BaseModel):
    raw_text: str | None = None
    locality: str | None = None
    city: str | None = None
    state: str | None = None
    country: str = "India"
    lat: float | None = None
    lon: float | None = None
    radius_m: float | None = None


class QueryInput(BaseModel):
    location: LocationInput
    keywords: list[str] = Field(..., min_length=1)
    exclude_keywords: list[str] = []
    max_results: int = Field(default=500, ge=1, le=5000)
    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    enrich_websites: bool = True
    sources: set[str] = Field(
        default={"overture", "osm"},
        description="Enabled sources: overture|osm|wikidata|alltheplaces|imports",
    )
    cache_policy: str = Field(
        default="auto",
        description="Cache policy for Overture data: auto | force_fresh | prefer_cache",
    )
    max_cache_age_days: int = Field(
        default=30,
        ge=0,
        le=365,
        description="Maximum age in days for a cached Overture extract",
    )


class CreateRunResponse(BaseModel):
    run_id: str
    status: str = "queued"
    created_at: datetime


class RunCard(BaseModel):
    id: str
    status: str
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    locality: str | None = None
    city: str | None = None
    state: str | None = None
    country: str = "India"
    keywords: list[str] = []
    stats: dict[str, Any] | None = None
    geo_confidence: float | None = None
    boundary_kind: str | None = None
    batch_id: str | None = None
    error: str | None = None
    error_code: str | None = None
    failed_node: str | None = None
    degraded: list[str] = []
    retryable: bool = True
    attempt_count: int = 0
    attempt_strategy: str | None = None
    parent_run_id: str | None = None
    completion_reason: str | None = None


class BatchRunRequest(BaseModel):
    keywords: list[str]
    city: str
    region: str
    options: dict[str, Any] = {}


def _row_to_runcard(r: Any) -> RunCard:
    d = dict(r)
    d["id"] = str(d.get("id"))
    if d.get("parent_run_id"):
        d["parent_run_id"] = str(d["parent_run_id"])

    # Stats parsing
    stats_data: Any = d.get("stats")
    if isinstance(stats_data, str):
        try:
            stats_data = json.loads(stats_data)
        except Exception as e:
            log.warning("Could not parse stats JSON in _row_to_runcard", error=str(e))
            stats_data = {}
    d["stats"] = stats_data if isinstance(stats_data, dict) else None

    # Error & failure telemetry
    err_val = d.get("error")
    if err_val and isinstance(err_val, str) and err_val.startswith("{"):
        try:
            err_dict = json.loads(err_val)
            d["error"] = err_dict.get("message") or err_val
            d["failed_node"] = err_dict.get("node")
            if not d.get("error_code"):
                d["error_code"] = err_dict.get("code") or err_dict.get("error_code")
            if "retryable" in err_dict:
                d["retryable"] = bool(err_dict["retryable"])
        except Exception as e:
            log.warning("Could not parse error payload in _row_to_runcard", error=str(e))
    else:
        d["error"] = err_val

    # Retryable safety: corrupt rows are never retryable
    if d.get("error_code") == "corrupt_run_row" or d.get("retryable") is False:
        d["retryable"] = False

    # Keywords & degraded safety
    d["keywords"] = d.get("keywords") or []
    d["degraded"] = d.get("degraded") or (stats_data.get("degraded", []) if isinstance(stats_data, dict) else [])

    return RunCard(**d)


# ── Routes ────────────────────────────────────────────────────────────────────

def _assert_worker_available(request: Request) -> Any:
    worker = getattr(request.app.state, "worker", None)
    if not worker:
        if "pytest" in sys.modules or getattr(settings, "testing", False):
            worker = RunWorker(event_bus=get_bus(), concurrency=2)
            request.app.state.worker = worker
            return worker
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Runs cannot be queued right now — the worker is unavailable.",
                "code": "worker_unavailable",
                "reason": "Run worker is not mounted or initialized.",
                "action": "Ensure backend startup contract passes and worker is running.",
            },
        )
    if getattr(worker, "is_fatal", False) or getattr(worker, "health_state", "healthy") == "fatal":
        err_msg = getattr(worker, "_fatal_error", None) or (worker.health.last_error if hasattr(worker, "health") else None)
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Runs cannot be queued right now — the worker is in a fatal error state.",
                "code": "worker_unavailable",
                "reason": err_msg or "Database schema or permission error in worker.",
                "action": "Run: uv run alembic upgrade head, then restart the backend.",
            },
        )
    return worker


@router.post("/runs", status_code=202, response_model=CreateRunResponse)
async def create_run(body: QueryInput, request: Request) -> CreateRunResponse:
    """Create a new run and enqueue it. Returns 202 immediately if worker is healthy, else 503."""
    worker = _assert_worker_available(request)

    run_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    async with get_conn() as conn:
        await conn.execute(
            """
            INSERT INTO query_runs
              (id, created_at, status, raw_input, locality, city, state, country, keywords, exclude_keywords, options)
            VALUES
              (%s, %s, 'queued', %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                run_id,
                now,
                Jsonb(body.model_dump(mode="json")),
                body.location.locality,
                body.location.city,
                body.location.state,
                body.location.country,
                list(body.keywords),
                list(body.exclude_keywords),
                Jsonb({"enrich_websites": body.enrich_websites, "sources": sorted(body.sources)}),
            ),
        )
        await conn.commit()

    # Enqueue without blocking the HTTP response
    await worker.enqueue(run_id)

    return CreateRunResponse(run_id=run_id, created_at=now)


@router.post("/runs/batch", status_code=202)
async def create_batch_run(body: BatchRunRequest, request: Request) -> dict[str, Any]:
    """Create runs for all areas in a city/region from area_seeds."""
    worker = _assert_worker_available(request)
    batch_id = str(uuid.uuid4())

    async with get_conn() as conn:
        rows = await (await conn.execute(
            "SELECT area FROM area_seeds WHERE city = %s AND (region = %s OR locality = %s) ORDER BY area",
            (body.city, body.region, body.region),
        )).fetchall()

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"No areas found for city='{body.city}' region='{body.region}'.",
        )

    run_ids = []
    worker = getattr(request.app.state, "worker", None)
    for row in rows:
        area = row.get("area") or row.get("locality")
        q = QueryInput(
            location=LocationInput(locality=area, city=body.city, country="India"),
            keywords=body.keywords,
            **body.options,
        )
        run_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        async with get_conn() as conn:
            await conn.execute(
                """
                INSERT INTO query_runs
                  (id, created_at, status, raw_input, locality, city, keywords, batch_id)
                VALUES (%s, %s, 'queued', %s, %s, %s, %s, %s)
                """,
                (run_id, now, Jsonb(q.model_dump(mode="json")), area, body.city, list(body.keywords), batch_id),
            )
            await conn.commit()
        if worker:
            await worker.enqueue(run_id)
        run_ids.append(run_id)

    return {"batch_id": batch_id, "run_count": len(run_ids), "run_ids": run_ids}


@router.get("/runs", response_model=list[RunCard])
async def list_runs(
    cursor: str | None = None,
    status: str | None = None,
    q: str | None = None,
    limit: int = 50,
) -> list[RunCard]:
    """Paginated list of runs, most recent first."""
    conditions: list[sql.Composable] = []
    params: list[Any] = []

    if status:
        conditions.append(sql.SQL("status = %s"))
        params.append(status)
    if q:
        conditions.append(sql.SQL("(locality ILIKE %s OR city ILIKE %s OR %s = ANY(keywords))"))
        params.extend([f"%{q}%", f"%{q}%", q])
    if cursor:
        conditions.append(sql.SQL("created_at < %s"))
        params.append(cursor)

    where_clause = (
        sql.SQL("WHERE ") + sql.SQL(" AND ").join(conditions)
        if conditions
        else sql.SQL("")
    )
    params.append(limit)

    async with get_conn() as conn:
        run_query = sql.SQL("SELECT * FROM query_runs {} ORDER BY created_at DESC LIMIT %s").format(
            where_clause
        )
        rows = await (await conn.execute(run_query, params)).fetchall()

    return [_row_to_runcard(r) for r in rows]


@router.get("/runs/{run_id}", response_model=RunCard)
async def get_run(run_id: str) -> RunCard:
    async with get_conn() as conn:
        row = await (await conn.execute(
            "SELECT * FROM query_runs WHERE id = %s", (run_id,)
        )).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return _row_to_runcard(row)


@router.get("/runs/{run_id}/events")
async def run_events(run_id: str, request: Request) -> StreamingResponse:
    """SSE stream for a run. Events come from the in-memory event bus."""
    bus = request.app.state.event_bus

    async def generate() -> AsyncIterator[str]:
        q = await bus.subscribe(run_id)
        try:
            while True:
                try:
                    event: SSEEvent | None = await asyncio.wait_for(
                        q.get(), timeout=HEARTBEAT_INTERVAL
                    )
                    if event is None:
                        yield "event: done\ndata: {}\n\n"
                        return
                    yield event.encode()
                except asyncio.TimeoutError:
                    yield f"event: heartbeat\ndata: {{}}\n\n"
        finally:
            await bus.unsubscribe(run_id, q)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.post("/runs/{run_id}/resume")
async def resume_run(run_id: str, body: dict[str, Any], request: Request) -> dict[str, str]:
    config = {"configurable": {"thread_id": run_id}}
    graph = get_compiled_graph()
    asyncio.create_task(
        graph.astream({"disambiguation_choice": body.get("choice_id")}, config=config)
    )
    return {"status": "resumed", "run_id": run_id}


@router.post("/runs/{run_id}/cancel")
async def cancel_run(run_id: str, request: Request) -> dict[str, str]:
    worker = getattr(request.app.state, "worker", None) if request and hasattr(request, "app") else None
    if worker and hasattr(worker, "cancel_run"):
        await worker.cancel_run(run_id)
    else:
        async with get_conn() as conn:
            await conn.execute(
                "UPDATE query_runs SET status = 'cancelled', finished_at = NOW() WHERE id = %s AND status IN ('queued', 'running')",
                (run_id,),
            )
            await conn.commit()
    bus = get_bus()
    await bus.publish(run_id, "run_cancelled", {"run_id": run_id, "status": "cancelled"})
    return {"status": "cancelled", "run_id": run_id}


@router.post("/runs/{run_id}/rerun", status_code=202, response_model=CreateRunResponse)
async def rerun(run_id: str, request: Request) -> CreateRunResponse:
    async with get_conn() as conn:
        row = await (await conn.execute(
            "SELECT raw_input, locality, city, state, keywords, retryable, attempt_count, error_code FROM query_runs WHERE id = %s",
            (run_id,)
        )).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    # 1. Server-side retryable verification
    if row.get("retryable") is False or row.get("error_code") == "corrupt_run_row":
        raise HTTPException(
            status_code=422,
            detail={
                "code": "not_retryable",
                "message": "This run can't be re-run — its original query data is missing or corrupted.",
                "action": "Start a new search with the same locality and keywords.",
                "prefill": {
                    "locality": row.get("locality"),
                    "city": row.get("city"),
                    "state": row.get("state"),
                    "keywords": row.get("keywords") or [],
                },
            },
        )

    raw = row.get("raw_input")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception as e:
            log.warning("Failed to parse raw_input as JSON", exc=str(e), run_id=run_id)
            raw = None

    if not isinstance(raw, dict) or not raw:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "not_retryable",
                "message": "This run can't be re-run — its original query data is missing.",
                "action": "Start a new search with the same locality and keywords.",
                "prefill": {
                    "locality": row.get("locality"),
                    "city": row.get("city"),
                    "state": row.get("state"),
                    "keywords": row.get("keywords") or [],
                },
            },
        )

    try:
        body = QueryInput(**raw)
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "not_retryable",
                "message": f"Stored query data is invalid: {e}",
                "prefill": {
                    "locality": row.get("locality"),
                    "city": row.get("city"),
                    "state": row.get("state"),
                    "keywords": row.get("keywords") or [],
                },
            },
        )

    # Dispatch retry with linked parent_run_id and incremented attempt_count
    worker = _assert_worker_available(request)
    new_run_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    new_attempt_count = (row.get("attempt_count") or 0) + 1

    async with get_conn() as conn:
        await conn.execute(
            """
            INSERT INTO query_runs
              (id, created_at, status, raw_input, locality, city, state, country, keywords, exclude_keywords, options, retryable, attempt_count, parent_run_id)
            VALUES
              (%s, %s, 'queued', %s, %s, %s, %s, %s, %s, %s, %s, TRUE, %s, %s)
            """,
            (
                new_run_id,
                now,
                Jsonb(body.model_dump(mode="json")),
                body.location.locality,
                body.location.city,
                body.location.state,
                body.location.country,
                list(body.keywords),
                list(body.exclude_keywords),
                Jsonb({"enrich_websites": body.enrich_websites, "sources": sorted(body.sources)}),
                new_attempt_count,
                run_id,
            ),
        )
        await conn.commit()

    await worker.enqueue(new_run_id)
    return CreateRunResponse(run_id=new_run_id, created_at=now)


@router.post("/runs/clear-failed")
async def clear_failed_runs() -> dict[str, Any]:
    """Delete unretryable and failed legacy runs."""
    async with get_conn() as conn:
        res = await conn.execute(
            """
            DELETE FROM query_runs
             WHERE status = 'failed' AND (retryable = FALSE OR error_code = 'corrupt_run_row')
            RETURNING id
            """
        )
        deleted = await res.fetchall()
        await conn.commit()
    return {"deleted_count": len(deleted), "run_ids": [str(r["id"]) for r in deleted]}

