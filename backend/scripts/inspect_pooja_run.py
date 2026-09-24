"""
Inspect Specific Pooja Store Run in HSR Layout
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
            # Find runs for pooja store
            runs = await (await conn.execute(
                """
                SELECT id, status, started_at, finished_at, stats, error
                  FROM query_runs
                 WHERE raw_input::text ILIKE '%pooja store%' AND raw_input::text ILIKE '%HSR Layout%'
                 ORDER BY created_at DESC
                 LIMIT 3
                """
            )).fetchall()

            print("=======================================================")
            print(f"POOJA STORE RUNS FOUND: {len(runs)}")
            print("=======================================================")

            for r in runs:
                run_id = str(r["id"])
                print(f"\nRun ID: {run_id}")
                print(f"Status: {r['status']}")
                print(f"Started: {r['started_at']} | Finished: {r['finished_at']}")
                print(f"Error: {r['error']}")
                stats = r["stats"] or {}
                print(f"Candidates Found: {stats.get('candidate_count', 0)}")
                print(f"Resolved Entities: {stats.get('resolved_entity_count', 0)}")
                print(f"Source Stats: {stats.get('source_stats', {})}")
                print(f"Metrics: {stats.get('metrics', {})}")

                # Accepted businesses for this run
                businesses = await (await conn.execute(
                    """
                    SELECT b.canonical_name, b.primary_category, b.phones_e164, b.emails, b.website_url, b.confidence, b.tier, rr.rank
                      FROM run_results rr
                      JOIN businesses b ON rr.business_id = b.id
                     WHERE rr.run_id = %s
                     ORDER BY rr.rank ASC
                    """,
                    (run_id,),
                )).fetchall()

                print(f"\nAccepted Businesses for {run_id} ({len(businesses)} rows):")
                for b in businesses:
                    print(f"  #{b['rank']}: {b['canonical_name']} | Cat: {b['primary_category']} | Conf: {b['confidence']} | Tier: {b['tier']} | Phones: {b['phones_e164']} | URL: {b['website_url']}")

                # Rejected candidates for this run
                rejected = await (await conn.execute(
                    """
                    SELECT source, name, reason, reason_code, relevance_p
                      FROM rejected_candidates
                     WHERE run_id = %s
                     LIMIT 5
                    """,
                    (run_id,),
                )).fetchall()

                print(f"\nSample Rejected Candidates for {run_id} ({len(rejected)} rows):")
                for rej in rejected:
                    print(f"  - {rej['name']} ({rej['source']}) -> Reason: {rej['reason']} (Code: {rej['reason_code']})")

    finally:
        await close_pools()


if __name__ == "__main__":
    asyncio.run(main())
