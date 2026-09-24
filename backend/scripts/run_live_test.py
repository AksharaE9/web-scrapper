"""
Live End-to-End Pipeline Execution & Verification Script

Submits a live query: 'pooja store · HSR Layout, Bengaluru',
executes it with the leased RunWorker,
and prints the database evidence.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
import uuid

if hasattr(sys.stdout, "reconfigure"):
    try:
        fn_out = getattr(sys.stdout, "reconfigure", None)
        if callable(fn_out):
            fn_out(encoding="utf-8", errors="replace")
        fn_err = getattr(sys.stderr, "reconfigure", None)
        if callable(fn_err):
            fn_err(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import structlog
from app.db.pool import close_pools, get_conn, init_pools
from app.events.bus import EventBus
from app.worker import RunWorker

log = structlog.get_logger()


async def run_live_test() -> None:
    run_id = str(uuid.uuid4())
    raw_input = {
        "keywords": ["pooja store"],
        "location": {
            "locality": "HSR Layout",
            "city": "Bengaluru",
            "state": "Karnataka",
            "country": "India",
        },
        "sources": ["overture", "osm"],
        "max_results": 25,
        "enrich_websites": True,
    }

    print(f"\n=======================================================")
    print(f"[RUN] Submitting Live Run: {run_id}")
    print(f"Target: pooja store · HSR Layout, Bengaluru")
    print(f"=======================================================\n")

    await init_pools()
    try:
        async with get_conn() as conn:
            # Mark any stale queued/running runs as cancelled so this test runs immediately
            await conn.execute("UPDATE query_runs SET status = 'cancelled' WHERE status IN ('queued', 'running')")
            await conn.execute(
                """
                INSERT INTO query_runs (id, raw_input, status, created_at, updated_at)
                VALUES (%s, %s, 'queued', NOW(), NOW())
                """,
                (run_id, json.dumps(raw_input)),
            )
            await conn.commit()

        bus = EventBus()
        worker = RunWorker(event_bus=bus, concurrency=2, poll_interval_s=0.5)

        print("Starting RunWorker...")
        await worker.start()

        # Wait for run completion
        max_wait_seconds = 180
        elapsed = 0
        final_status = "unknown"

        while elapsed < max_wait_seconds:
            await asyncio.sleep(2.0)
            elapsed += 2
            async with get_conn() as conn:
                row = await (await conn.execute(
                    "SELECT status, stats, error, finished_at FROM query_runs WHERE id = %s", (run_id,)
                )).fetchone()

            if row:
                st = row["status"]
                print(f"[{elapsed:03d}s] Status: {st}")
                if st in ("completed", "failed", "cancelled"):
                    final_status = st
                    break

        await worker.stop()

        print(f"\n=======================================================")
        print(f"[SUMMARY] Run Finished with Status: {final_status}")
        print(f"=======================================================\n")

        async with get_conn() as conn:
            run_row = await (await conn.execute(
                "SELECT id, status, stats, error, started_at, finished_at FROM query_runs WHERE id = %s", (run_id,)
            )).fetchone()

            businesses_rows = await (await conn.execute(
                """
                SELECT b.id, b.canonical_name, b.primary_category, b.phones_e164, b.emails, b.website_url, b.confidence, b.tier, rr.rank
                  FROM run_results rr
                  JOIN businesses b ON rr.business_id = b.id
                 WHERE rr.run_id = %s
                 ORDER BY rr.rank ASC
                 LIMIT 10
                """,
                (run_id,),
            )).fetchall()

            rejected_rows = await (await conn.execute(
                """
                SELECT source, name, reason
                  FROM rejected_candidates
                 WHERE run_id = %s
                 LIMIT 5
                """,
                (run_id,),
            )).fetchall()

        print(f"Run Row: {json.dumps(dict(run_row) if run_row else {}, default=str, indent=2)}")
        print(f"\nAccepted Businesses ({len(businesses_rows)} sample):")
        for b in businesses_rows:
            print(f"  #{b['rank']}: {b['canonical_name']} | Tier: {b['tier']} | Conf: {b['confidence']} | Phones: {b['phones_e164']}")

        print(f"\nRejected Candidates ({len(rejected_rows)} sample):")
        for r in rejected_rows:
            print(f"  - {r['name']} ({r['source']}) -> Reason: {r['reason']}")

    finally:
        await close_pools()


if __name__ == "__main__":
    asyncio.run(run_live_test())
