"""
A2 Regression Test — Extension Verification
Queries pg_extension, asserts all four (postgis, pg_trgm, vector, citext) are present, and logs versions.
"""

import pytest
from app.db import pool as db_pool

REQUIRED_EXTENSIONS = {"postgis", "pg_trgm", "vector", "citext"}

@pytest.mark.asyncio
async def test_required_extensions() -> None:
    async with db_pool.get_conn() as conn:
        cursor = await conn.execute(
            "SELECT extname, extversion FROM pg_extension WHERE extname = ANY(%s)",
            (list(REQUIRED_EXTENSIONS),),
        )
        rows = await cursor.fetchall()
        installed = {r["extname"]: r["extversion"] for r in rows} if rows and isinstance(rows[0], dict) else {r[0]: r[1] for r in rows}
        
        missing = REQUIRED_EXTENSIONS - set(installed.keys())
        assert not missing, f"Missing required database extensions: {missing}. Installed: {installed}"

