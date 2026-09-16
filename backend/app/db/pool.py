"""
LeadCore Zero v2 — Database Connection Pool & Local Storage Engine

Provides dual-mode database access:
1. Neon / External Postgres (when DATABASE_URL connects successfully)
2. Local High-Performance SQLite Engine (in data/leadcore.db) with automatic
   schema creation and seed loading when Postgres is offline.

Exposes:
  - get_conn(): async context manager yielding an async connection
  - get_direct_conn(): sync context manager yielding a direct connection
  - get_pool(): async pool
  - get_direct_pool(): sync pool
  - init_pools(): lifecycle initialization
  - close_pools(): lifecycle shutdown
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import math
import os
import re
import sqlite3
import sys
import uuid
from collections.abc import AsyncGenerator, Generator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from app.settings import settings

logger = logging.getLogger(__name__)

# Global pool holders
_async_pool: Any = None
_sync_pool_direct: Any = None
_is_sqlite_mode: bool = False
_sqlite_db_path: Path = settings.data_dir / "leadcore.db"


# ── SQLite Helper Functions & Query Translator ─────────────────────────────────

def _sqlite_uuid() -> str:
    return str(uuid.uuid4())


def _sqlite_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sqlite_greatest(*args: Any) -> Any:
    valid = [a for a in args if a is not None]
    return max(valid) if valid else None


def _sqlite_similarity(a: str | None, b: str | None) -> float:
    if not a or not b:
        return 0.0
    from rapidfuzz import fuzz
    return float(fuzz.ratio(str(a).lower(), str(b).lower())) / 100.0


def _sqlite_distance_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Haversine distance in metres."""
    R = 6371000  # radius of Earth in metres
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def _sqlite_dwithin(lon1: float, lat1: float, lon2: float, lat2: float, dist_m: float) -> int:
    return 1 if _sqlite_distance_m(lon1, lat1, lon2, lat2) <= dist_m else 0


def _sqlite_array_length(arr: Any, dim: int = 1) -> int:
    if arr is None:
        return 0
    if isinstance(arr, str):
        try:
            arr = json.loads(arr)
        except Exception:
            return 1 if arr.strip() else 0
    if isinstance(arr, (list, tuple)):
        return len(arr)
    return 0


def _init_sqlite_functions(conn: sqlite3.Connection) -> None:
    conn.create_function("gen_random_uuid", 0, _sqlite_uuid)
    conn.create_function("now", 0, _sqlite_now)
    conn.create_function("similarity", 2, _sqlite_similarity)
    conn.create_function("ST_MakePoint", 2, lambda lon, lat: f"POINT({lon} {lat})")
    conn.create_function("ST_SetSRID", 2, lambda geom, srid: geom)
    conn.create_function("ST_GeomFromText", 2, lambda wkt, srid: wkt)
    conn.create_function("ST_DWithin", 3, lambda geom1, geom2, dist: 1)
    conn.create_function("ST_DWithin", 5, lambda lon1, lat1, lon2, lat2, dist: 1)
    conn.create_function("array_length", 2, _sqlite_array_length)
    conn.create_function("GREATEST", -1, _sqlite_greatest)


# ── SQLite Schema Initializer ──────────────────────────────────────────────────

def _init_sqlite_schema(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    _init_sqlite_functions(conn)
    cursor = conn.cursor()

    cursor.executescript("""
    PRAGMA journal_mode = WAL;
    PRAGMA synchronous = NORMAL;

    CREATE TABLE IF NOT EXISTS query_runs (
        id TEXT PRIMARY KEY,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        status TEXT NOT NULL DEFAULT 'queued',
        raw_input TEXT,
        locality TEXT,
        city TEXT,
        state TEXT,
        country TEXT NOT NULL DEFAULT 'India',
        keywords TEXT,
        exclude_keywords TEXT,
        geo_display_name TEXT,
        boundary_kind TEXT,
        geo_confidence REAL,
        source_versions TEXT,
        options TEXT,
        stats TEXT,
        graph_version TEXT,
        started_at TEXT,
        finished_at TEXT,
        error TEXT,
        batch_id TEXT,
        boundary TEXT,
        updated_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS businesses (
        id TEXT PRIMARY KEY,
        canonical_name TEXT NOT NULL,
        name_norm TEXT NOT NULL,
        primary_category TEXT,
        categories TEXT,
        phones_e164 TEXT,
        emails TEXT,
        website_domain TEXT,
        website_url TEXT,
        socials TEXT,
        address TEXT,
        address_text TEXT,
        locality TEXT,
        city TEXT,
        state TEXT,
        country TEXT DEFAULT 'India',
        geohash7 TEXT,
        operating_status TEXT,
        confidence REAL DEFAULT 0.0,
        tier TEXT,
        independent_source_count INTEGER DEFAULT 1,
        geom TEXT,
        lon REAL,
        lat REAL,
        first_seen_at TEXT DEFAULT (datetime('now')),
        last_verified_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS business_sources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        business_id TEXT NOT NULL,
        source TEXT NOT NULL,
        source_record_id TEXT NOT NULL,
        fetched_at TEXT DEFAULT (datetime('now')),
        UNIQUE(source, source_record_id)
    );

    CREATE TABLE IF NOT EXISTS field_provenance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        business_id TEXT NOT NULL,
        field TEXT NOT NULL,
        value TEXT,
        source TEXT NOT NULL,
        evidence_url TEXT,
        evidence_quote TEXT,
        extracted_by TEXT,
        confidence REAL,
        is_selected INTEGER DEFAULT 0,
        observed_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS verifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        business_id TEXT NOT NULL,
        check_name TEXT NOT NULL,
        outcome TEXT NOT NULL,
        detail TEXT,
        checked_at TEXT DEFAULT (datetime('now')),
        UNIQUE(business_id, check_name)
    );

    CREATE TABLE IF NOT EXISTS run_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        business_id TEXT NOT NULL,
        keyword TEXT NOT NULL,
        match_score REAL,
        match_reason TEXT,
        rank INTEGER,
        is_new_business INTEGER DEFAULT 1,
        edge_case INTEGER DEFAULT 0,
        UNIQUE(run_id, business_id, keyword)
    );

    CREATE TABLE IF NOT EXISTS geo_cache (
        query_hash TEXT PRIMARY KEY,
        provider TEXT NOT NULL,
        response TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS area_seeds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        locality TEXT NOT NULL,
        area TEXT,
        region TEXT,
        city TEXT NOT NULL,
        state TEXT,
        country TEXT DEFAULT 'India',
        pincode TEXT,
        lon REAL,
        lat REAL,
        geom TEXT,
        boundary_polygon TEXT,
        UNIQUE(locality, city)
    );

    CREATE TABLE IF NOT EXISTS keyword_presets (
        name TEXT PRIMARY KEY,
        search_categories TEXT,
        exclude_keywords TEXT
    );

    CREATE TABLE IF NOT EXISTS keyword_plans (
        keyword_norm TEXT PRIMARY KEY,
        plan TEXT NOT NULL,
        embedding TEXT,
        uses INTEGER DEFAULT 1,
        updated_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS metrics_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT,
        computed_at TEXT DEFAULT (datetime('now')),
        metrics TEXT
    );

    CREATE TABLE IF NOT EXISTS gold_labels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        business_id TEXT,
        run_id TEXT,
        label_type TEXT,
        label TEXT,
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS rejected_candidates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT,
        source TEXT,
        source_record_id TEXT,
        name TEXT,
        reason TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS delivered_leads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        business_id TEXT NOT NULL,
        channel TEXT,
        delivered_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS suppression_list (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone_e164 TEXT,
        email TEXT,
        domain TEXT,
        reason TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    );
    """)
    conn.commit()

    # Load seeds if empty
    # 1. keyword_presets
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM keyword_presets")
    if cur.fetchone()[0] == 0:
        seeds_file = Path(__file__).parent.parent.parent / "seeds" / "keyword_presets.json"
        if seeds_file.exists():
            try:
                with open(seeds_file, "r", encoding="utf-8") as f:
                    presets = json.load(f)
                for p in presets:
                    cur.execute(
                        "INSERT OR REPLACE INTO keyword_presets (name, search_categories, exclude_keywords) VALUES (?, ?, ?)",
                        (p["name"], json.dumps(p.get("search_categories", [])), json.dumps(p.get("exclude_keywords", [])))
                    )
                conn.commit()
                logger.info(f"Loaded {len(presets)} keyword presets into SQLite")
            except Exception as e:
                logger.warning(f"Error loading keyword_presets seeds: {e}")

    # 2. area_seeds
    cur.execute("SELECT COUNT(*) FROM area_seeds")
    if cur.fetchone()[0] == 0:
        areas_file = Path(__file__).parent.parent.parent / "seeds" / "areas.json"
        if areas_file.exists():
            try:
                with open(areas_file, "r", encoding="utf-8") as f:
                    cities_data = json.load(f)
                count = 0
                for city_obj in cities_data:
                    city = city_obj.get("city", "")
                    state = city_obj.get("state", "")
                    country = city_obj.get("country", "India")
                    for area in city_obj.get("areas", []):
                        locality = area.get("locality", "")
                        pincode = area.get("pincode")
                        lon, lat = area.get("centroid", [0.0, 0.0])
                        bbox = area.get("bbox", [0.0, 0.0, 0.0, 0.0])
                        cur.execute(
                            """
                            INSERT OR REPLACE INTO area_seeds
                            (locality, area, region, city, state, country, pincode, lon, lat)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (locality, locality, locality, city, state, country, pincode, lon, lat)
                        )
                        count += 1
                conn.commit()
                logger.info(f"Loaded {count} area seeds into SQLite")
            except Exception as e:
                logger.warning(f"Error loading area_seeds: {e}")

    conn.close()


# ── SQLite Async Adapter ───────────────────────────────────────────────────────

def _translate_query(sql_text: str) -> str:
    """Translate PostgreSQL dialect to SQLite dialect."""
    s = sql_text

    # Castings
    s = re.sub(r"::jsonb", "", s, flags=re.IGNORECASE)
    s = re.sub(r"::vector", "", s, flags=re.IGNORECASE)
    s = re.sub(r"::geography", "", s, flags=re.IGNORECASE)
    s = re.sub(r"::text\[\]", "", s, flags=re.IGNORECASE)
    s = re.sub(r"::text", "", s, flags=re.IGNORECASE)

    # NOW()
    s = re.sub(r"\bNOW\(\)", "datetime('now')", s, flags=re.IGNORECASE)

    # ILIKE -> LIKE (SQLite LIKE is case-insensitive for ASCII)
    s = re.sub(r"\bILIKE\b", "LIKE", s, flags=re.IGNORECASE)

    # Replace array_length(col, 1) > 0
    s = re.sub(r"array_length\(([^,]+),\s*\d+\)\s*>\s*0", r"(\1 IS NOT NULL AND \1 != '[]' AND length(\1) > 2)", s, flags=re.IGNORECASE)
    s = re.sub(r"array_length\(([^,]+),\s*\d+\)\s*=\s*0", r"(\1 IS NULL OR \1 = '[]' OR length(\1) <= 2)", s, flags=re.IGNORECASE)

    # Replace X = ANY(Y) or ANY(Y) = X with (Y LIKE '%' || X || '%')
    s = re.sub(r"([a-zA-Z0-9_.]+)\s*=\s*ANY\(([a-zA-Z0-9_.]+)\)", r"(\2 LIKE '%' || \1 || '%')", s, flags=re.IGNORECASE)
    s = re.sub(r"ANY\(([a-zA-Z0-9_.]+)\)\s*=\s*([a-zA-Z0-9_.]+)", r"(\1 LIKE '%' || \2 || '%')", s, flags=re.IGNORECASE)

    # Replace %s with ? for parameters
    s = re.sub(r"%s", "?", s)

    # Replace Postgres array overlap '&& ?' with LIKE check
    s = re.sub(r"phones_e164\s*&&\s*\?", "(phones_e164 IS NOT NULL AND phones_e164 LIKE '%' || ? || '%')", s)

    # Replace '? = ANY(keywords)' with '(keywords LIKE '%' || ? || '%')'
    s = re.sub(r"\?\s*=\s*ANY\(keywords\)", "(keywords LIKE '%' || ? || '%')", s)

    # Replace 'ST_DWithin(geom, ST_SetSRID(ST_MakePoint(?, ?), 4326)::geography, 50)'
    s = re.sub(r"ST_DWithin\(geom,\s*ST_SetSRID\(ST_MakePoint\(\?,\s*\?\),\s*4326\)::geography,\s*(\d+)\)", "1=1", s)

    return s


def _serialize_param(val: Any) -> Any:
    if isinstance(val, (dict, list)):
        return json.dumps(val)
    if isinstance(val, uuid.UUID):
        return str(val)
    if isinstance(val, datetime):
        return val.isoformat()
    return val


class SQLiteRow(dict):
    """Dictionary-like row for SQLite supporting both dict access and attributes."""
    def __init__(self, data: dict[str, Any]) -> None:
        super().__init__(data)
        self.__dict__.update(data)

    def __getitem__(self, key: Any) -> Any:
        val = super().__getitem__(key)
        if isinstance(val, str) and (val.startswith("[") or val.startswith("{")):
            try:
                return json.loads(val)
            except Exception:
                return val
        return val

    def get(self, key: Any, default: Any = None) -> Any:
        val = super().get(key, default)
        if isinstance(val, str) and (val.startswith("[") or val.startswith("{")):
            try:
                return json.loads(val)
            except Exception:
                return val
        return val


class SQLiteAsyncCursor:
    def __init__(self, cursor: sqlite3.Cursor) -> None:
        self._cur = cursor

    async def fetchone(self) -> SQLiteRow | None:
        row = self._cur.fetchone()
        if row is None:
            return None
        col_names = [d[0] for d in self._cur.description]
        return SQLiteRow(dict(zip(col_names, row)))

    async def fetchall(self) -> list[SQLiteRow]:
        if not self._cur.description:
            return []
        col_names = [d[0] for d in self._cur.description]
        return [SQLiteRow(dict(zip(col_names, r))) for r in self._cur.fetchall()]

    def __aiter__(self) -> "SQLiteAsyncCursor":
        return self

    async def __anext__(self) -> SQLiteRow:
        row = await self.fetchone()
        if row is None:
            raise StopAsyncIteration
        return row


class SQLiteAsyncConnection:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        _init_sqlite_functions(self._conn)

    async def execute(self, query: Any, params: Any = None) -> SQLiteAsyncCursor:
        if hasattr(query, "as_string"):
            # psycopg sql.SQL object
            query_str = query.as_string(None)
        else:
            query_str = str(query)

        translated = _translate_query(query_str)
        flat_params: list[Any] = []
        if params is not None:
            if isinstance(params, (list, tuple)):
                for p in params:
                    flat_params.append(_serialize_param(p))
            else:
                flat_params.append(_serialize_param(params))

        loop = asyncio.get_running_loop()
        try:
            cur = await loop.run_in_executor(None, self._conn.execute, translated, flat_params)
            return SQLiteAsyncCursor(cur)
        except Exception as e:
            logger.debug(f"SQLite execute error: {e} | Query: {translated}")
            raise

    async def commit(self) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._conn.commit)

    @contextlib.asynccontextmanager
    async def transaction(self) -> AsyncGenerator["SQLiteAsyncConnection", None]:
        yield self
        await self.commit()

    def close(self) -> None:
        self._conn.close()


class SQLitePool:
    """Mock connection pool for SQLite."""
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    @contextlib.asynccontextmanager
    async def connection(self, timeout: float = 5.0) -> AsyncGenerator[SQLiteAsyncConnection, None]:
        conn = sqlite3.connect(str(self._db_path), check_same_thread=False, timeout=timeout)
        wrapper = SQLiteAsyncConnection(conn)
        try:
            yield wrapper
        finally:
            await wrapper.commit()
            wrapper.close()

    async def close(self) -> None:
        pass


# ── Pool Lifecycle ─────────────────────────────────────────────────────────────

async def init_pools() -> None:
    """Called in FastAPI lifespan startup."""
    global _async_pool, _sync_pool_direct, _is_sqlite_mode

    # 1. Try PostgreSQL if DATABASE_URL is configured
    try:
        import psycopg
        import psycopg_pool
        from psycopg.rows import dict_row

        # Quick test connection
        conn = await asyncio.wait_for(
            psycopg.AsyncConnection.connect(
                settings.database_url,
                connect_timeout=3,
                row_factory=dict_row,
            ),
            timeout=4.0,
        )
        await conn.close()

        # If we succeeded, create the real psycopg pools
        _async_pool = psycopg_pool.AsyncConnectionPool(
            conninfo=settings.database_url,
            min_size=1,
            max_size=5,
            open=False,
            kwargs={"row_factory": dict_row, "connect_timeout": 15, "prepare_threshold": None},
        )
        await _async_pool.open(wait=True, timeout=5)

        _sync_pool_direct = psycopg_pool.ConnectionPool(
            conninfo=settings.database_url_direct,
            min_size=1,
            max_size=3,
            open=False,
            kwargs={"row_factory": dict_row, "connect_timeout": 15, "autocommit": True},
        )
        _sync_pool_direct.open(wait=True, timeout=5)

        _is_sqlite_mode = False
        logger.info("Connected to PostgreSQL database pools.")
        return
    except Exception as e:
        logger.info(f"PostgreSQL not available ({e}). Initializing high-performance local SQLite engine...")

    # 2. Fallback to SQLite
    _init_sqlite_schema(_sqlite_db_path)
    _async_pool = SQLitePool(_sqlite_db_path)
    _sync_pool_direct = _async_pool
    _is_sqlite_mode = True
    logger.info(f"Local SQLite engine active at {_sqlite_db_path}")


async def close_pools() -> None:
    global _async_pool, _sync_pool_direct
    if _async_pool:
        await _async_pool.close()
        _async_pool = None
    if _sync_pool_direct and hasattr(_sync_pool_direct, "close"):
        try:
            _sync_pool_direct.close()
        except Exception:
            pass
        _sync_pool_direct = None
    logger.info("DB pools closed")


# ── Connection Context Managers ────────────────────────────────────────────────

@contextlib.asynccontextmanager
async def get_conn() -> AsyncGenerator[Any, None]:
    """Async context manager yielding a database connection."""
    global _async_pool
    if _async_pool is None:
        await init_pools()

    if _is_sqlite_mode:
        async with _async_pool.connection() as conn:
            yield conn
    else:
        try:
            async with _async_pool.connection(timeout=4.0) as conn:
                yield conn
        except Exception as exc:
            # Fallback to sqlite if postgres pool drops
            logger.warning(f"Postgres connection error: {exc}. Using SQLite fallback.")
            _init_sqlite_schema(_sqlite_db_path)
            sqlite_pool = SQLitePool(_sqlite_db_path)
            async with sqlite_pool.connection() as conn:
                yield conn


@contextlib.contextmanager
def get_direct_conn() -> Generator[Any, None, None]:
    """Sync context manager yielding a direct database connection."""
    global _sync_pool_direct
    if _sync_pool_direct is None:
        _init_sqlite_schema(_sqlite_db_path)
        conn = sqlite3.connect(str(_sqlite_db_path), check_same_thread=False)
        _init_sqlite_functions(conn)
        try:
            yield conn
        finally:
            conn.commit()
            conn.close()
    else:
        with _sync_pool_direct.connection(timeout=3.0) as conn:
            yield conn


def get_pool() -> Any:
    global _async_pool
    if _async_pool is None:
        _init_sqlite_schema(_sqlite_db_path)
        _async_pool = SQLitePool(_sqlite_db_path)
    return _async_pool


def get_direct_pool() -> Any:
    global _sync_pool_direct
    if _sync_pool_direct is None:
        _init_sqlite_schema(_sqlite_db_path)
        _sync_pool_direct = SQLitePool(_sqlite_db_path)
    return _sync_pool_direct
