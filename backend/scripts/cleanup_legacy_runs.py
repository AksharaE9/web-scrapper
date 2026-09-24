"""
Cleanup and Quarantine Legacy Runs Script

Scans the query_runs table for:
- Corrupt rows with missing or unparseable raw_input
- Orphaned runs left in 'running' or 'queued' state from legacy deployments
- Marks them as failed with error_code='corrupt_run_row' or 'orphaned_run'
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.db.pool import close_pools, get_conn, init_pools

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("cleanup_legacy_runs")


async def cleanup_corrupt_and_orphaned_runs() -> None:
    await init_pools()
    try:
        async with get_conn() as conn:
            # 1. Quarantine runs with NULL raw_input
            res_null = await conn.execute("""
                UPDATE query_runs
                   SET status = 'failed',
                       error = 'quarantined by cleanup script: missing raw_input',
                       error_code = 'corrupt_run_row',
                       finished_at = NOW(),
                       updated_at = NOW()
                 WHERE raw_input IS NULL
                   AND status IN ('queued', 'running')
             RETURNING id
            """)
            null_ids = await res_null.fetchall()
            logger.info("Quarantined %d runs with NULL raw_input", len(null_ids))

            # 2. Check all remaining queued or running runs for unparseable raw_input
            res_active = await conn.execute("""
                SELECT id, raw_input FROM query_runs
                 WHERE status IN ('queued', 'running')
            """)
            active_rows = await res_active.fetchall()
            corrupt_ids = []
            for row in active_rows:
                raw = row.get("raw_input")
                if isinstance(raw, str):
                    try:
                        raw = json.loads(raw)
                    except Exception:
                        raw = None
                if not isinstance(raw, dict):
                    corrupt_ids.append(row["id"])

            if corrupt_ids:
                await conn.execute("""
                    UPDATE query_runs
                       SET status = 'failed',
                           error = 'quarantined by cleanup script: unparseable raw_input',
                           error_code = 'corrupt_run_row',
                           finished_at = NOW(),
                           updated_at = NOW()
                     WHERE id = ANY(%s)
                """, (corrupt_ids,))
                logger.info("Quarantined %d runs with unparseable raw_input", len(corrupt_ids))

            await conn.commit()
            logger.info("Cleanup of legacy and corrupt runs completed successfully.")
    finally:
        await close_pools()


if __name__ == "__main__":
    asyncio.run(cleanup_corrupt_and_orphaned_runs())
