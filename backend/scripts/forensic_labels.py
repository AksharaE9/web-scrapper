import asyncio
from app.db.pool import init_pools, get_pool, close_pools


async def main():
    await init_pools()
    async with get_pool().connection() as conn:
        # Check if relevance_labels table exists
        cur = await conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_name = 'relevance_labels'"
        )
        exists = await cur.fetchone()
        if not exists:
            print("TABLE relevance_labels does NOT exist — no labels to quarantine")
            await close_pools()
            return

        # A.6 forensic query — businesses with multiple labels (stale-closure signature)
        cur = await conn.execute("""
            SELECT business_id, count(*) AS n_labels,
                   min(created_at) AS first, max(created_at) AS last,
                   count(DISTINCT verdict) AS distinct_verdicts
            FROM relevance_labels
            GROUP BY business_id
            HAVING count(*) > 1
            ORDER BY n_labels DESC
            LIMIT 20
        """)
        rows = await cur.fetchall()
        print(f"Suspect labels (businesses with >1 label): {len(rows)}")
        for r in rows:
            span = (r["last"] - r["first"]).total_seconds()
            print(f"  business_id={r['business_id']}  n_labels={r['n_labels']}  "
                  f"distinct_verdicts={r['distinct_verdicts']}  span={span:.1f}s")

        # Overall label count
        cur = await conn.execute("SELECT count(*) FROM relevance_labels")
        total = (await cur.fetchone())[0]
        print(f"\nTotal labels in DB: {total}")

        # Check for rapid-fire labels within 5 seconds (stale closure signature)
        cur = await conn.execute("""
            SELECT business_id, count(*) AS n_labels,
                   min(created_at) AS first, max(created_at) AS last
            FROM relevance_labels
            GROUP BY business_id
            HAVING count(*) > 1
               AND EXTRACT(EPOCH FROM (max(created_at) - min(created_at))) < 5
            ORDER BY n_labels DESC
        """)
        rapid = await cur.fetchall()
        print(f"\nRapid-fire labels (<5s between labels on same business): {len(rapid)}")
        for r in rapid:
            span = (r["last"] - r["first"]).total_seconds()
            print(f"  SUSPECT  business_id={r['business_id']}  n={r['n_labels']}  span={span:.2f}s")

    await close_pools()


asyncio.run(main())
