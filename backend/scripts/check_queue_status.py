import asyncio
import sys
sys.path.insert(0, ".")
from app.db.pool import get_conn, init_pools, close_pools

async def main():
    await init_pools()
    try:
        async with get_conn() as conn:
            res = await conn.execute(
                "SELECT column_name, data_type FROM information_schema.columns WHERE table_name='query_runs' AND column_name IN ('worker_id','lease_until','error_code')"
            )
            cols = await res.fetchall()
            print("COLUMNS IN query_runs:")
            for c in cols:
                print(f"  {c['column_name']} ({c['data_type']})")
                
            res2 = await conn.execute(
                "SELECT status, count(*) as count, min(created_at) AS oldest FROM query_runs GROUP BY status ORDER BY status"
            )
            statuses = await res2.fetchall()
            print("\nSTATUS SUMMARY:")
            for s in statuses:
                print(f"  status={s['status']}: count={s['count']}, oldest={s['oldest']}")
    finally:
        await close_pools()

if __name__ == "__main__":
    asyncio.run(main())
