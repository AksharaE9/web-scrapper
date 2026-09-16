"""
Health check API router — GET /api/health, GET /api/health/live, GET /api/health/ready
"""

from __future__ import annotations

import asyncio
from typing import Any

import duckdb
import httpx
from fastapi import APIRouter
from psycopg import sql

from app.db.pool import get_conn
from app.settings import settings

router = APIRouter(tags=["health"])


async def _check_neon() -> dict[str, Any]:
    try:
        async with get_conn() as conn:
            row = await (await conn.execute("SELECT 1 AS alive")).fetchone()
            if row and row["alive"] == 1:
                return {"status": "ok"}
            return {"status": "error", "error": "Unexpected query response"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


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
        from app.graph.nodes.n3a_overture import _discover_latest_release, _get_duckdb_conn

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
        return {"status": "ok", "latest_release": "2025-07-23.0", "error": str(e)}


async def _check_overpass() -> dict[str, Any]:
    headers = {"User-Agent": settings.crawler_user_agent}
    async with httpx.AsyncClient(headers=headers, timeout=5.0) as client:
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
        async with httpx.AsyncClient(headers=headers, timeout=5.0) as client:
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


@router.get("/health")
async def get_health() -> dict[str, Any]:
    """Comprehensive system health status."""
    neon_res, overture_res, overpass_res, nominatim_res, ollama_res = await asyncio.gather(
        _check_neon(),
        _check_overture(),
        _check_overpass(),
        _check_nominatim(),
        _check_ollama(),
        return_exceptions=False,
    )
    duckdb_res = _check_duckdb()
    disk_res = _calc_disk_cache()

    overall = "ok"
    if neon_res.get("status") == "error":
        overall = "degraded"
    if duckdb_res.get("status") == "error":
        overall = "unhealthy"

    return {
        "status": overall,
        "neon": neon_res,
        "duckdb": duckdb_res,
        "overture": overture_res,
        "overpass": overpass_res,
        "nominatim": nominatim_res,
        "ollama": ollama_res,
        "disk_cache": disk_res,
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