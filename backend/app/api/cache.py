"""
Cache Management API — LeadCore Zero

Provides endpoints to inspect, purge, and rebuild geospatial and Overture tile caches.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any
from fastapi import APIRouter

from app.settings import settings

router = APIRouter(prefix="/cache", tags=["cache"])


@router.get("/overture/stats")
async def get_overture_cache_stats() -> dict[str, Any]:
    """Return overview of cached Overture parquet files and disk usage."""
    cache_dir = settings.overture_cache_dir
    if not cache_dir.exists():
        return {"total_files": 0, "size_mb": 0.0, "releases": []}

    total_size = 0
    total_files = 0
    releases = []

    for rel_dir in cache_dir.iterdir():
        if rel_dir.is_dir() and not rel_dir.name.startswith("."):
            rel_files = list(rel_dir.glob("*.parquet"))
            rel_size = sum(f.stat().st_size for f in rel_files)
            total_size += rel_size
            total_files += len(rel_files)
            releases.append({
                "release": rel_dir.name,
                "file_count": len(rel_files),
                "size_mb": round(rel_size / (1024 * 1024), 2),
            })

    return {
        "total_files": total_files,
        "size_mb": round(total_size / (1024 * 1024), 2),
        "releases": releases,
    }


@router.post("/overture/purge")
async def purge_overture_cache() -> dict[str, Any]:
    """Purge all cached Overture parquet files and sidecar metadata."""
    cache_dir = settings.overture_cache_dir
    purged_count = 0
    if cache_dir.exists():
        for item in cache_dir.iterdir():
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
                purged_count += 1
            elif item.is_file():
                item.unlink(missing_ok=True)
                purged_count += 1

    cache_dir.mkdir(parents=True, exist_ok=True)
    return {
        "status": "ok",
        "message": "Overture cache successfully purged",
        "purged_directories": purged_count,
    }
