"""
scripts/audit/reset_queue.py — Reset queued/running stale runs to cancelled so audit scenarios run immediately.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from app.db.pool import get_conn, init_pools, close_pools


async def reset_stale_runs() -> None:
    await init_pools()
    try:
        async with get_conn() as conn:
            await conn.execute(
                """
                UPDATE query_runs
                SET status = 'cancelled'
                WHERE status IN ('queued', 'running')
                """
            )
            await conn.commit()
            print("Successfully cleared stale queued/running runs.")
    finally:
        await close_pools()


if __name__ == "__main__":
    asyncio.run(reset_stale_runs())
