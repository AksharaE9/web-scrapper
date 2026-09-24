import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.pool import init_pools, get_conn

async def main():
    await init_pools()
    async with get_conn() as conn:
        rows = await (await conn.execute(
            """
            SELECT *
            FROM query_runs
            ORDER BY created_at DESC
            LIMIT 10
            """
        )).fetchall()
        
        print(f"Found {len(rows)} recent runs:")
        for r in rows:
            print("="*60)
            print("RUN ID:", r["id"])
            print("Status:", r["status"])
            print("Keywords:", r.get("keywords"))
            print("Locality / City:", r.get("locality"), r.get("city"))
            print("Source Stats:", json.dumps(r.get("source_stats"), indent=2, default=str) if r.get("source_stats") else "NULL")
            print("Outcome Table:", json.dumps(r.get("outcome_table"), indent=2, default=str) if r.get("outcome_table") else "NULL")
            print("Failure Reason:", r.get("failure_reason"))

if __name__ == "__main__":
    asyncio.run(main())
