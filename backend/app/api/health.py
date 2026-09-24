"""
Health check API router — GET /api/health, GET /api/health/live, GET /api/health/ready
"""

from __future__ import annotations

import asyncio
from typing import Any

import duckdb
import httpx
import structlog
from fastapi import APIRouter, Request
from psycopg import sql

from langgraph.checkpoint.memory import MemorySaver

from app.db.pool import get_conn
from app.graph.nodes.n3a_overture import _discover_latest_release, _get_duckdb_conn
from app.obs.loop_monitor import get_max_loop_lag_ms_60s
from app.settings import settings

log = structlog.get_logger()

router = APIRouter(tags=["health"])


def _inspect_checkpointer(cp: Any | None) -> dict[str, Any]:
    if cp is None:
        # Fallback to compiled graph checkpointer if available
        try:
            from app.graph.build import get_compiled_graph  # allowed-lazy-import: avoid circular dependency with graph build
            cg = get_compiled_graph()
            cp = getattr(cg, "checkpointer", None)
        except Exception:
            pass

    if cp is None:
        return {
            "class": "None",
            "module": "builtins",
            "is_durable": False,
            "is_async_capable": False,
        }
    is_memory = type(cp).__name__ in ("MemorySaver", "InMemorySaver") or isinstance(cp, MemorySaver)
    return {
        "class": type(cp).__name__,
        "module": type(cp).__module__,
        "is_durable": not is_memory,
        "is_async_capable": hasattr(cp, "aput"),
    }


async def _check_neon(cp: Any | None = None) -> dict[str, Any]:
    try:
        async with get_conn() as conn:
            cursor = await conn.execute("SELECT version() AS pg_version")
            row = await cursor.fetchone()
            ext_cursor = await conn.execute("SELECT extname, extversion FROM pg_extension")
            ext_rows = await ext_cursor.fetchall()
            exts = {r["extname"]: r["extversion"] for r in ext_rows}
            return {
                "status": "ok",
                "engine": "postgresql",
                "version": row["pg_version"].split(",")[0] if row else "unknown",
                "extensions": exts,
                "checkpointer": _inspect_checkpointer(cp),
            }
    except Exception as e:
        return {"status": "error", "error": str(e), "checkpointer": _inspect_checkpointer(cp)}


def _check_duckdb() -> dict[str, Any]:
    try:
        con = duckdb.connect()
        res = con.execute("SELECT 1").fetchone()
        con.close()
        if res and res[0] == 1:
            return {"status": "ok"}
        return {"status": "error", "error": "Query returned unexpected result"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def _check_overture() -> dict[str, Any]:
    try:
        # Run discovery in threadpool to avoid blocking event loop
        def discover() -> str:
            con = _get_duckdb_conn()
            try:
                return _discover_latest_release(con)
            finally:
                con.close()

        release = await asyncio.to_thread(discover)
        return {"status": "ok", "latest_release": release}
    except Exception as e:
        return {"status": "degraded", "error": str(e), "latest_release": None}


def _calc_overture_cache_info() -> dict[str, Any]:
    """
    Scan .meta.json sidecars in the Overture cache directory to report:
    - Total cache size in MB
    - Newest cache release
    - Newest cache age in days
    """
    import json
    from datetime import datetime, timezone
    cache_dir = settings.overture_cache_dir
    if not cache_dir.exists():
        return {"size_mb": 0.0, "newest_release": None, "newest_age_days": None}

    total_bytes = 0
    newest_written_at = None
    newest_release = None

    for meta_file in cache_dir.rglob("*.meta.json"):
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            parquet = meta_file.with_suffix(".parquet")
            if parquet.exists():
                total_bytes += parquet.stat().st_size
            written_at_str = meta.get("written_at")
            if written_at_str:
                written_at = datetime.fromisoformat(written_at_str)
                if written_at.tzinfo is None:
                    written_at = written_at.replace(tzinfo=timezone.utc)
                if newest_written_at is None or written_at > newest_written_at:
                    newest_written_at = written_at
                    newest_release = meta.get("release")
        except Exception:
            continue

    # Also count parquet files that have no .meta.json (legacy)
    for parquet in cache_dir.rglob("*.parquet"):
        if not parquet.with_suffix(".meta.json").exists():
            try:
                total_bytes += parquet.stat().st_size
            except Exception:
                pass

    age_days = None
    if newest_written_at:
        delta = datetime.now(timezone.utc) - newest_written_at
        age_days = round(delta.total_seconds() / 86400, 1)

    return {
        "size_mb": round(total_bytes / (1024 * 1024), 2),
        "newest_release": newest_release,
        "newest_cache_age_days": age_days,
    }


async def _check_overpass() -> dict[str, Any]:
    headers = {"User-Agent": settings.crawler_user_agent}
    async with httpx.AsyncClient(headers=headers, timeout=2.0) as client:
        for ep in settings.overpass_endpoints:
            try:
                base_ep = ep.rsplit("/interpreter", 1)[0]
                r = await client.get(f"{base_ep}/status")
                if r.status_code == 200:
                    return {"status": "ok", "endpoint": ep}
            except Exception:
                continue
    return {"status": "error", "error": "All Overpass endpoints unreachable"}


async def _check_nominatim() -> dict[str, Any]:
    headers = {"User-Agent": settings.crawler_user_agent}
    try:
        async with httpx.AsyncClient(headers=headers, timeout=2.0) as client:
            r = await client.get(f"{settings.nominatim_url}/status.php")
            if r.status_code == 200:
                return {"status": "ok"}
            # Fallback check
            r = await client.get(f"{settings.nominatim_url}/search?format=json&q=test&limit=1")
            if r.status_code == 200:
                return {"status": "ok"}
            return {"status": "error", "error": f"Status HTTP {r.status_code}"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def _check_ollama() -> dict[str, Any]:
    if not settings.llm_enabled:
        return {"status": "disabled", "model": settings.ollama_model}

    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            r = await client.get(f"{settings.ollama_url}/api/tags")
            if r.status_code == 200:
                data = r.json()
                models = [m.get("name", "") for m in data.get("models", [])]
                matched = any(settings.ollama_model in m for m in models)
                return {
                    "status": "ok" if matched else "degraded",
                    "model": settings.ollama_model,
                    "available_models": models,
                }
            return {"status": "error", "error": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"status": "error", "error": str(e), "model": settings.ollama_model}


def _calc_disk_cache() -> dict[str, Any]:
    try:
        if not settings.data_dir.exists():
            return {"size_mb": 0.0}
        total_bytes = sum(f.stat().st_size for f in settings.data_dir.rglob("*") if f.is_file())
        return {"size_mb": round(total_bytes / (1024 * 1024), 2)}
    except Exception:
        return {"size_mb": 0.0}


async def _check_queue(worker: Any | None) -> dict[str, Any]:
    worker_health = worker.health.to_dict() if worker and hasattr(worker, "health") else {
        "state": "stopped",
        "worker_id": "uninitialized",
        "active_runs": 0,
        "free_slots": 0,
        "last_successful_claim_at": None,
        "last_poll_at": None,
        "last_error": "Worker not mounted on app.state",
        "error_code": "worker_uninitialized",
        "consecutive_errors": 0,
    }

    depth: dict[str, Any] = {
        "queued": 0,
        "running": 0,
        "oldest_queued_age_s": 0,
        "oldest_queued_run_id": None,
    }
    throughput: dict[str, Any] = {
        "completed_last_hour": 0,
        "failed_last_hour": 0,
    }

    try:
        async with get_conn() as conn:
            d_res = await conn.execute(
                """
                SELECT 
                    COUNT(*) FILTER (WHERE status = 'queued') as queued,
                    COUNT(*) FILTER (WHERE status = 'running') as running,
                    COALESCE(EXTRACT(EPOCH FROM (NOW() - MIN(created_at) FILTER (WHERE status = 'queued')))::int, 0) as oldest_queued_age_s,
                    (SELECT id FROM query_runs WHERE status = 'queued' ORDER BY created_at ASC LIMIT 1) as oldest_queued_run_id
                FROM query_runs
                """
            )
            d_row = await d_res.fetchone()
            if d_row:
                depth = {
                    "queued": int(d_row["queued"] or 0),
                    "running": int(d_row["running"] or 0),
                    "oldest_queued_age_s": int(d_row["oldest_queued_age_s"] or 0),
                    "oldest_queued_run_id": str(d_row["oldest_queued_run_id"]) if d_row["oldest_queued_run_id"] else None,
                }

            t_res = await conn.execute(
                """
                SELECT 
                    COUNT(*) FILTER (WHERE status = 'completed' AND finished_at > NOW() - INTERVAL '1 hour') as completed_last_hour,
                    COUNT(*) FILTER (WHERE status = 'failed' AND finished_at > NOW() - INTERVAL '1 hour') as failed_last_hour
                FROM query_runs
                """
            )
            t_row = await t_res.fetchone()
            if t_row:
                throughput = {
                    "completed_last_hour": int(t_row["completed_last_hour"] or 0),
                    "failed_last_hour": int(t_row["failed_last_hour"] or 0),
                }
    except Exception as e:
        log.error("Failed to compute queue health metrics", error=str(e))

    return {
        "worker": worker_health,
        "depth": depth,
        "throughput": throughput,
    }


@router.get("/health")
async def get_health(request: Request) -> dict[str, Any]:
    """Comprehensive system health status including leased worker queue health."""
    worker = getattr(request.app.state, "worker", None) if request and hasattr(request, "app") else None
    checkpointer = getattr(request.app.state, "checkpointer", None) if request and hasattr(request, "app") else None

    neon_res, overture_res, overpass_res, nominatim_res, ollama_res, queue_res = await asyncio.gather(
        _check_neon(checkpointer),
        _check_overture(),
        _check_overpass(),
        _check_nominatim(),
        _check_ollama(),
        _check_queue(worker),
        return_exceptions=False,
    )
    duckdb_res = _check_duckdb()
    disk_res = _calc_disk_cache()
    overture_cache_info = _calc_overture_cache_info()
    loop_lag = get_max_loop_lag_ms_60s()

    overall = "ok"
    if neon_res.get("status") == "error":
        overall = "degraded"
    if duckdb_res.get("status") == "error":
        overall = "unhealthy"

    cp_info = neon_res.get("checkpointer", {})
    if not getattr(settings, "testing", False) and not cp_info.get("is_durable", True):
        overall = "unhealthy"

    worker_state = queue_res.get("worker", {}).get("state")
    queued_count = queue_res.get("depth", {}).get("queued", 0)
    oldest_queued_age = queue_res.get("depth", {}).get("oldest_queued_age_s", 0)

    # If worker is fatal or unhealthy, system is unhealthy
    if worker_state in ("fatal", "unhealthy"):
        overall = "unhealthy"
    # If queue is backed up with no progress (>120s and worker not healthy), mark unhealthy
    elif queued_count > 0 and oldest_queued_age > 120 and worker_state != "healthy":
        overall = "unhealthy"
    elif queued_count > 0 and oldest_queued_age > 300:
        overall = "degraded"
    elif overture_res.get("status") == "degraded" and overall == "ok":
        overall = "degraded"

    return {
        "status": overall,
        "checkpointer": cp_info,
        "max_loop_lag_ms_60s": loop_lag,
        "neon": neon_res,
        "duckdb": duckdb_res,
        "overture": {**overture_res, **overture_cache_info},
        "overpass": overpass_res,
        "nominatim": nominatim_res,
        "ollama": ollama_res,
        "disk_cache": disk_res,
        "queue": queue_res,
    }


@router.get("/health/live")
async def live_probe() -> dict[str, str]:
    """Kubernetes / container liveness probe."""
    return {"status": "live"}


@router.get("/health/ready")
async def ready_probe() -> dict[str, Any]:
    """Readiness probe checking critical dependencies."""
    duckdb_res = _check_duckdb()
    neon_res = await _check_neon()
    ready = duckdb_res.get("status") == "ok"
    return {
        "ready": ready,
        "duckdb": duckdb_res,
        "neon": neon_res,
    }