"""
LeadCore Zero v2 — FastAPI Application

Lifespan:
  1. Initialise Neon connection pools (pooled + direct)
  2. Start bounded async run worker
  3. Initialise in-memory SSE event bus

Runs are never executed inside HTTP handlers.
POST /api/runs returns 202 immediately; the worker executes the graph.
SSE events come from the in-memory bus (not Neon polling).
"""

from __future__ import annotations

import asyncio
import io
import logging
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

# ── Windows UTF-8 fix ─────────────────────────────────────────────────────────
# structlog rich tracebacks contain Unicode box-drawing chars (U+250x) which
# cp1252 (Windows default) cannot encode → UnicodeEncodeError that masks the
# real error.  Reconfigure stdout/stderr to UTF-8 before anything is logged.
if sys.platform == "win32":
    for _stream_name in ("stdout", "stderr"):
        _stream = getattr(sys, _stream_name)
        if hasattr(_stream, "buffer") and getattr(_stream, "encoding", "").lower() != "utf-8":
            setattr(
                sys,
                _stream_name,
                io.TextIOWrapper(_stream.buffer, encoding="utf-8", errors="replace"),
            )

if sys.platform == "win32" and sys.version_info < (3, 14):
    try:
        _set_policy = getattr(asyncio, "set_event_loop_policy", None)
        _selector_policy = getattr(asyncio, "WindowsSelectorEventLoopPolicy", None)
        if _set_policy and _selector_policy:
            _set_policy(_selector_policy())
    except Exception:
        pass
    try:
        import uvicorn.loops.asyncio
        uvicorn.loops.asyncio.asyncio_loop_factory = lambda use_subprocess=False: asyncio.SelectorEventLoop
    except Exception:
        pass



import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    cache,
    concepts,
    config,
    geo,
    health,
    keywords,
    labels,
    leads,
    metrics,
    presets,
    runs,
)
from app.db.pool import close_pools, get_conn, init_pools
from app.db.schema_contract import assert_migrations_current, assert_schema
from app.events.bus import EventBus, get_bus
from app.graph.build import build_checkpointer, get_compiled_graph
from app.graph.runtime import set_event_bus
from app.obs.loop_monitor import start_loop_monitor, stop_loop_monitor
from app.settings import settings
from app.worker import RunWorker

# ── Logging setup ─────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(asctime)s [%(levelname)-8s] %(message)s",
)
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
)
log = structlog.get_logger()


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    log.info("LeadCore Zero v2 starting up")

    # 1. Neon connection pools
    await init_pools()
    log.info("Database pools initialised")

    # 2. Schema contract & migration enforcement (refuse to start if broken/drifted)
    async with get_conn() as conn:
        await assert_schema(conn)
        await assert_migrations_current(conn)
    log.info("Database schema contract and migrations verified")

    # 3. Concept Cards Catalog & Taxonomy validation
    from app.relevance.concepts import load_all_cards
    from app.taxonomy.foundry import get_taxonomy_spine
    cards = load_all_cards()
    spine = get_taxonomy_spine()
    if len(cards) < 20:
        raise RuntimeError(f"Concept Catalog missing or insufficient ({len(cards)} cards loaded). Refusing to boot.")
    log.info("Concept card catalog verified", cards_count=len(cards), taxonomy_categories=len(spine.categories))

    # 4. In-memory SSE event bus & loop monitor
    event_bus = get_bus()
    app.state.event_bus = event_bus
    set_event_bus(event_bus)
    start_loop_monitor()

    # 4. Ensure LangGraph checkpointer and tables exist (durable AsyncPostgresSaver)
    checkpointer = await build_checkpointer()
    app.state.checkpointer = checkpointer
    compiled = get_compiled_graph(checkpointer=checkpointer)
    log.info("LangGraph checkpointer verified/created", checkpointer=type(checkpointer).__name__)

    # 5. Bounded run worker (resumes in-flight runs from checkpoints)
    worker = RunWorker(event_bus=event_bus, concurrency=settings.run_concurrency)
    await worker.start()
    app.state.worker = worker
    log.info("Run worker started", worker_id=worker.worker_id, concurrency=settings.run_concurrency)

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────
    log.info("LeadCore Zero v2 shutting down")
    stop_loop_monitor()
    await worker.stop()
    await close_pools()
    log.info("Shutdown complete")


# ── App ───────────────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title="LeadCore Zero v2",
        description=(
            "Graph-engineered, keyless, local-first lead intelligence scraper. "
            "₹0 running cost. No API keys."
        ),
        version="2.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # GZip compression for large GeoJSON boundaries and lead arrays
    from starlette.middleware.gzip import GZipMiddleware
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # CORS — configured from settings, never hard-coded
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ───────────────────────────────────────────────────────────
    app.include_router(health.router, prefix="/api")
    app.include_router(config.router, prefix="/api")
    app.include_router(cache.router, prefix="/api")
    app.include_router(runs.router, prefix="/api")
    app.include_router(leads.router, prefix="/api")
    app.include_router(concepts.router, prefix="/api")
    app.include_router(geo.router, prefix="/api")
    app.include_router(keywords.router, prefix="/api")
    app.include_router(presets.router, prefix="/api")
    app.include_router(metrics.router, prefix="/api")
    app.include_router(labels.router, prefix="/api")

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True, loop="asyncio")
