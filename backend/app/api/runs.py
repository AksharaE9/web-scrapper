"""
Runs API router — POST /api/runs, GET /api/runs, GET /api/runs/{id}, SSE, cancel, rerun.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from psycopg import sql
from pydantic import BaseModel, Field

from app.db.pool import get_conn
from app.events.bus import HEARTBEAT_INTERVAL, SSEEvent

router = APIRouter(tags=["runs"])


# ── Request / Response models ──────────────────────────────────────────────────

class LocationInput(BaseModel):
    raw_text: str | None = None
    locality: str | None = None
    city: str | None = None
    state: str | None = None
    country: str = "India"


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


class BatchRunRequest(BaseModel):
    keywords: list[str]
    city: str
    region: str
    options: dict[str, Any] = {}


def _row_to_runcard(r: Any) -> RunCard:
    d = dict(r)
    d["id"] = str(d.get("id"))
    if isinstance(d.get("keywords"), str):
        try:
            d["keywords"] = json.loads(d["keywords"])
        except Exception:
            d["keywords"] = [d["keywords"]] if d["keywords"] else []
    elif not d.get("keywords"):
        d["keywords"] = []

    if isinstance(d.get("created_at"), str):
        try:
            d["created_at"] = datetime.fromisoformat(d["created_at"])
        except Exception:
            d["created_at"] = datetime.now(timezone.utc)
    elif not d.get("created_at"):
        d["created_at"] = datetime.now(timezone.utc)

    if isinstance(d.get("started_at"), str):
        try:
            d["started_at"] = datetime.fromisoformat(d["started_at"])
        except Exception:
            d["started_at"] = None

    if isinstance(d.get("finished_at"), str):
        try:
            d["finished_at"] = datetime.fromisoformat(d["finished_at"])
        except Exception:
            d["finished_at"] = None

    if isinstance(d.get("stats"), str):
        try:
            d["stats"] = json.loads(d["stats"])
        except Exception:
            d["stats"] = {}

    return RunCard(**d)


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/runs", status_code=202, response_model=CreateRunResponse)
async def create_run(body: QueryInput, request: Request) -> CreateRunResponse:
    """Create a new run and enqueue it. Returns 202 immediately."""
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
                now.isoformat(),
                json.dumps(body.model_dump(mode="json")),
                body.location.locality,
                body.location.city,
                body.location.state,
                body.location.country,
                json.dumps(body.keywords),
                json.dumps(body.exclude_keywords),
                json.dumps({"enrich_websites": body.enrich_websites, "sources": list(body.sources)}),
            ),
        )
        await conn.commit()

    # Enqueue without blocking the HTTP response
    worker = getattr(request.app.state, "worker", None)
    if worker:
        await worker.enqueue(run_id)

    return CreateRunResponse(run_id=run_id, created_at=now)


@router.post("/runs/batch", status_code=202)
async def create_batch_run(body: BatchRunRequest, request: Request) -> dict[str, Any]:
    """Create runs for all areas in a city/region from area_seeds."""
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
                (run_id, now.isoformat(), json.dumps(q.model_dump(mode="json")), area, body.city, json.dumps(body.keywords), batch_id),
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
    from app.graph.build import get_compiled_graph
    config = {"configurable": {"thread_id": run_id}}
    graph = get_compiled_graph()
    asyncio.create_task(
        graph.astream({"disambiguation_choice": body.get("choice_id")}, config=config)
    )
    return {"status": "resumed", "run_id": run_id}


@router.post("/runs/{run_id}/cancel")
async def cancel_run(run_id: str) -> dict[str, str]:
    async with get_conn() as conn:
        await conn.execute(
            "UPDATE query_runs SET status = 'cancelled' WHERE id = %s AND status IN ('queued', 'running')",
            (run_id,),
        )
        await conn.commit()
    return {"status": "cancelled", "run_id": run_id}


@router.post("/runs/{run_id}/rerun", status_code=202, response_model=CreateRunResponse)
async def rerun(run_id: str, request: Request) -> CreateRunResponse:
    async with get_conn() as conn:
        row = await (await conn.execute(
            "SELECT raw_input FROM query_runs WHERE id = %s", (run_id,)
        )).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    raw = row["raw_input"]
    if isinstance(raw, str):
        raw = json.loads(raw)
    body = QueryInput(**raw)
    return await create_run(body, request)
