"""
app/sources/overture.py — DuckDB Overture Maps S3 Parquet reader with schema assertion.

Features:
- Connects anonymously to Overture S3 Parquet releases in us-west-2
- Schema-drift gate: asserts required columns (basic_category, taxonomy, names, geometry, etc.)
- City-level Parquet cache preventing redundant S3 downloads
- Bbox spatial predicate pushdown
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

import duckdb
from app.settings import settings

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = {
    "id", "names", "basic_category", "taxonomy",
    "confidence", "phones", "websites", "emails",
    "socials", "addresses", "brand", "operating_status",
    "sources", "geometry",
}

OVERTURE_S3_BASE = "s3://overturemaps-us-west-2/release"


def get_duckdb_conn() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute("SET s3_region='us-west-2';")
    con.execute("SET s3_access_key_id='';")     # anonymous access
    con.execute("SET s3_secret_access_key='';")
    return con


def discover_latest_release(con: duckdb.DuckDBPyConnection) -> str:
    try:
        result = con.execute(
            f"SELECT * FROM glob('{OVERTURE_S3_BASE}/*/theme=places/type=place/*.parquet') LIMIT 1"
        ).fetchone()
        if result:
            path = str(result[0])
            import re
            m = re.search(r"/release/([^/]+)/", path)
            if m:
                return m.group(1)
    except Exception as e:
        logger.warning(f"Overture release discovery failed: {e}")
    # Try finding newest locally cached release
    cache_dir = settings.overture_cache_dir
    if cache_dir.exists():
        releases = sorted([d.name for d in cache_dir.iterdir() if d.is_dir() and d.name], reverse=True)
        if releases:
            return releases[0]
    raise RuntimeError("Cannot reach Overture S3 to discover release and no local cache exists.")


def get_cache_path(release: str, bbox: tuple[float, float, float, float]) -> Path:
    bbox_hash = hashlib.sha256(f"{release}:{bbox}".encode()).hexdigest()[:16]
    p = settings.overture_cache_dir / release / f"{bbox_hash}.parquet"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def validate_schema(con: duckdb.DuckDBPyConnection, parquet_path: str) -> None:
    cols = {row[0] for row in con.execute(
        f"DESCRIBE SELECT * FROM read_parquet('{parquet_path}') LIMIT 0"
    ).fetchall()}
    missing = REQUIRED_COLUMNS - cols
    if missing:
        raise RuntimeError(
            f"Overture schema drift detected! Missing columns: {missing}. "
            "Update REQUIRED_COLUMNS to match current Overture Places schema."
        )
