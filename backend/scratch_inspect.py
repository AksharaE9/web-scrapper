import asyncio
from app.db.pool import get_conn, init_pools

async def check():
    await init_pools()
    async with get_conn() as conn:
        rows = await (await conn.execute(
            """
            SELECT rr.decision, rr.relevance_stage, rr.reasons, b.canonical_name, b.primary_category, b.raw_categories
            FROM run_results rr
            JOIN businesses b ON b.id = rr.business_id
            WHERE rr.run_id = %s
            """,
            ('dfee7226-f78b-4aa1-aeb3-e583b8f608fa',)
        )).fetchall()
        for r in rows:
            if 'divine' in r['canonical_name'].lower():
                print("FOUND:", dict(r))

if __name__ == "__main__":
    asyncio.run(check())
