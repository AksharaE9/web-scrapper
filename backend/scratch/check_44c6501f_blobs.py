import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.pool import init_pools, get_conn

async def main() -> None:
    await init_pools()
    async with get_conn() as conn:
        rows = await (await conn.execute(
            """
            SELECT thread_id, channel, type, blob
            FROM checkpoint_blobs
            WHERE thread_id LIKE '44c6501f%'
            """
        )).fetchall()
        
        print(f"Found {len(rows)} blobs for 44c6501f:")
        for r in rows:
            print("Channel:", r["channel"], "Type:", r["type"])
            try:
                # Type msgpack or json
                import msgpack
                val = msgpack.unpackb(r["blob"])
                print(f"  Unpacked {r['channel']}:", str(val)[:200])
                if r["channel"] in ("source_stats", "geo", "plans", "outcome_table"):
                    print("  Full:", json.dumps(val, indent=2, default=str))
            except Exception as e:
                print("  Blob raw len:", len(r["blob"]) if r["blob"] else 0)

if __name__ == "__main__":
    asyncio.run(main())
