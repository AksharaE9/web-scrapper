"""
LeadCore Zero v3 — Database Connection Pool (PostgreSQL / PostGIS / pgvector)

Provides robust connection pools to Neon / Postgres with:
  - Exponential backoff retry on cold-start connects (up to 5 attempts)
  - Explicit extension verification (postgis, pg_trgm, vector, citext)
  - Async connection pool (psycopg.AsyncConnectionPool) over pooled DATABASE_URL
  - Direct connection pool (psycopg.ConnectionPool / AsyncConnectionPool) over DATABASE_URL_DIRECT
  - No silent SQLite fallbacks or dialect degradation
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import sys
from collections.abc import AsyncGenerator, Generator
from typing import Any

if sys.platform == "win32" and sys.version_info < (3, 14):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool, ConnectionPool

from app.settings import settings

logger = logging.getLogger(__name__)

# Global pool holders
_async_pool: AsyncConnectionPool | None = None
_sync_pool_direct: ConnectionPool | None = None
_async_pool_direct: AsyncConnectionPool | None = None


async def _assert_extensions(conn: psycopg.AsyncConnection[Any]) -> None:
    """Verify required Postgres extensions exist and log versions."""
    required = {"postgis", "pg_trgm", "vector", "citext"}
    cursor = await conn.execute("SELECT extname, extversion FROM pg_extension")
    rows = await cursor.fetchall()
    installed = {r["extname"]: r["extversion"] for r in rows}
    missing = required - set(installed.keys())
    if missing:
        raise RuntimeError(
            f"Missing required Postgres extensions: {missing}. "
            f"Installed extensions: {installed}. "
            f"Run 'CREATE EXTENSION IF NOT EXISTS postgis, pg_trgm, vector, citext;' in your Neon/Postgres database."
        )
    logger.info("Postgres extensions verified: %s", installed)


async def init_pools() -> None:
    """Initialize async and direct connection pools with exponential backoff on cold starts."""
    global _async_pool, _sync_pool_direct, _async_pool_direct

    last_err: Exception | None = None
    for attempt in range(5):
        try:
            logger.info("Connecting to Postgres (attempt %d/5)...", attempt + 1)
            # Main async pooled pool
            _async_pool = AsyncConnectionPool(
                conninfo=settings.database_url,
                min_size=1,
                max_size=5,
                open=False,
                kwargs={
                    "row_factory": dict_row,
                    "connect_timeout": 30,
                    "prepare_threshold": None,  # Required behind PgBouncer / Neon pooler
                },
            )
            await _async_pool.open(wait=True, timeout=45)

            # Direct sync pool for migrations / direct maintenance
            _sync_pool_direct = ConnectionPool(
                conninfo=settings.database_url_direct,
                min_size=1,
                max_size=3,
                open=False,
                kwargs={
                    "row_factory": dict_row,
                    "connect_timeout": 30,
                    "prepare_threshold": None,
                },
            )
            _sync_pool_direct.open(wait=True, timeout=45)

            # Direct async pool for LangGraph checkpoint saver
            _async_pool_direct = AsyncConnectionPool(
                conninfo=settings.database_url_direct,
                min_size=1,
                max_size=3,
                open=False,
                kwargs={
                    "autocommit": True,
                    "row_factory": dict_row,
                    "connect_timeout": 30,
                    "prepare_threshold": None,
                },
            )
            await _async_pool_direct.open(wait=True, timeout=45)

            # Assert extensions on an active connection
            async with _async_pool.connection() as conn:
                await _assert_extensions(conn)

            logger.info("Postgres connection pools successfully initialized.")
            return

        except Exception as e:
            last_err = e
            logger.warning("Postgres connection attempt %d failed: %s", attempt + 1, e)
            if _async_pool:
                try:
                    await _async_pool.close()
                except Exception:
                    pass
                _async_pool = None
            if _sync_pool_direct:
                try:
                    _sync_pool_direct.close()
                except Exception:
                    pass
                _sync_pool_direct = None
            if _async_pool_direct:
                try:
                    await _async_pool_direct.close()
                except Exception:
                    pass
                _async_pool_direct = None

            if attempt < 4:
                sleep_secs = 2 ** attempt
                logger.info("Waiting %d seconds before retry...", sleep_secs)
                await asyncio.sleep(sleep_secs)

    raise RuntimeError(
        f"Cannot reach Postgres after 5 attempts: {last_err}. "
        f"LeadCore Zero requires Postgres with PostGIS and pgvector. "
        f"Check DATABASE_URL and ensure your Neon compute is not suspended or misconfigured."
    )


async def close_pools() -> None:
    """Close all connection pools gracefully."""
    global _async_pool, _sync_pool_direct, _async_pool_direct
    if _async_pool:
        await _async_pool.close()
        _async_pool = None
    if _sync_pool_direct:
        _sync_pool_direct.close()
        _sync_pool_direct = None
    if _async_pool_direct:
        await _async_pool_direct.close()
        _async_pool_direct = None
    logger.info("Postgres connection pools closed.")


def get_pool() -> AsyncConnectionPool:
    """Return the global async pool or raise if not initialized."""
    if _async_pool is None:
        raise RuntimeError("Async connection pool is not initialized. Call init_pools() first.")
    return _async_pool


def get_direct_pool() -> ConnectionPool:
    """Return the global direct sync pool or raise if not initialized."""
    if _sync_pool_direct is None:
        raise RuntimeError("Direct sync pool is not initialized. Call init_pools() first.")
    return _sync_pool_direct


def get_direct_async_pool() -> AsyncConnectionPool:
    """Return the global direct async pool or raise if not initialized."""
    if _async_pool_direct is None:
        raise RuntimeError("Direct async pool is not initialized. Call init_pools() first.")
    return _async_pool_direct


@contextlib.asynccontextmanager
async def get_conn() -> AsyncGenerator[psycopg.AsyncConnection[Any], None]:
    """Async context manager providing a connection from the async pool."""
    pool = get_pool()
    async with pool.connection() as conn:
        yield conn


@contextlib.contextmanager
def get_direct_conn() -> Generator[psycopg.Connection[Any], None, None]:
    """Sync context manager providing a connection from the direct sync pool."""
    pool = get_direct_pool()
    with pool.connection() as conn:
        yield conn
