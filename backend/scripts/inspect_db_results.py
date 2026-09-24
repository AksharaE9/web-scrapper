"""
Inspect Database Runs, Results, and Accepted Leads
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

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

from app.db.pool import close_pools, get_conn, init_pools


async def main() -> None:
    await init_pools()
    try:
        async with get_conn() as conn:
            # 1. Run status summary
            runs_summary = await (await conn.execute(
                "SELECT status, count(*) as count FROM query_runs GROUP BY status ORDER BY count DESC"
            )).fetchall()
            print("=======================================================")
            print("RUN STATUS COUNTS:")
            for s in runs_summary:
                print(f"  {s['status']}: {s['count']}")

            # 2. Latest runs
            runs = await (await conn.execute(
                "SELECT id, status, started_at, finished_at, stats, error, error_code FROM query_runs ORDER BY created_at DESC LIMIT 5"
            )).fetchall()
            print("\n=======================================================")
            print("LATEST RUNS:")
            for r in runs:
                print(f"\nRun ID: {r['id']}")
                print(f"  Status: {r['status']}")
                print(f"  Started: {r['started_at']} | Finished: {r['finished_at']}")
                print(f"  Error: {r['error']} (Code: {r['error_code']})")
                stats_str = json.dumps(r['stats'] if r['stats'] else {}, indent=2, default=str)
                print(f"  Stats:\n{stats_str}")

            # 3. Accepted businesses
            businesses = await (await conn.execute(
                """
                SELECT b.canonical_name, b.primary_category, b.phones_e164, b.website_url, b.confidence, b.tier, rr.rank, rr.run_id
                  FROM run_results rr
                  JOIN businesses b ON rr.business_id = b.id
                 ORDER BY rr.run_id, rr.rank ASC
                 LIMIT 25
                """
            )).fetchall()
            print("\n=======================================================")
            print(f"ACCEPTED BUSINESSES ({len(businesses)} rows):")
            for b in businesses:
                print(f"  #{b['rank']}: {b['canonical_name']} | Cat: {b['primary_category']} | Conf: {b['confidence']:.2f} | Tier: {b['tier']} | Phones: {b['phones_e164']} | URL: {b['website_url']}")

            # 4. Rejected candidates sample
            rejected = await (await conn.execute(
                """
                SELECT run_id, source, name, reason, reason_code, relevance_p
                  FROM rejected_candidates
                 LIMIT 10
                """
            )).fetchall()
            print("\n=======================================================")
            print(f"SAMPLE REJECTED CANDIDATES ({len(rejected)} rows):")
            for r in rejected:
                print(f"  - {r['name']} ({r['source']}) -> Reason: {r['reason']} (Code: {r['reason_code']}, P: {r['relevance_p']})")

    finally:
        await close_pools()


if __name__ == "__main__":
    asyncio.run(main())
