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
import logging
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

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

from app.db.pool import close_pools, init_pools
from app.events.bus import EventBus
from app.settings import settings
from app.worker import RunWorker

# ── Logging setup ─────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO)
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    logger_factory=structlog.PrintLoggerFactory(),
)
log = structlog.get_logger()


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    log.info("LeadCore Zero v2 starting up")

    from app.events.bus import get_bus
    from app.graph.runtime import set_event_bus

    # 1. Neon connection pools
    try:
        await init_pools()
        log.info("Database pools initialised")
    except Exception as e:
        log.warning("Database pool initialization deferred or failed", error=str(e))

    # 2. In-memory SSE event bus
    event_bus = get_bus()
    app.state.event_bus = event_bus
    set_event_bus(event_bus)

    # 3. Bounded run worker (resumes in-flight runs from checkpoints)
    worker = RunWorker(event_bus=event_bus, concurrency=settings.run_concurrency)
    try:
        await worker.start()
    except Exception as e:
        log.warning("Run worker startup warning", error=str(e))
    app.state.worker = worker
    log.info("Run worker started", concurrency=settings.run_concurrency)

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────
    log.info("LeadCore Zero v2 shutting down")
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

    # CORS — configured from settings, never hard-coded
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ───────────────────────────────────────────────────────────
    from app.api import geo, health, keywords, labels, leads, metrics, presets, runs

    app.include_router(health.router, prefix="/api")
    app.include_router(runs.router, prefix="/api")
    app.include_router(leads.router, prefix="/api")
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
