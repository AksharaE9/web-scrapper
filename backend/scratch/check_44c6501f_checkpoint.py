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
            SELECT thread_id, checkpoint_ns, checkpoint_id, checkpoint, metadata
            FROM checkpoints
            WHERE thread_id LIKE '44c6501f%'
            ORDER BY checkpoint_id DESC
            LIMIT 5
            """
        )).fetchall()
        
        print(f"Found {len(rows)} checkpoints for 44c6501f:")
        for r in rows:
            print("="*60)
            print("Thread ID:", r["thread_id"])
            print("Checkpoint ID:", r["checkpoint_id"])
            cp = r["checkpoint"]
            if isinstance(cp, str):
                cp = json.loads(cp)
            
            channel_values = cp.get("channel_values", {})
            print("Channel keys:", list(channel_values.keys()))
            print("Source stats in checkpoint:")
            print(json.dumps(channel_values.get("source_stats"), indent=2, default=str))
            print("Geo resolution in checkpoint:")
            geo = channel_values.get("geo")
            print(json.dumps(geo, indent=2, default=str))
            print("Plans in checkpoint:")
            plans = channel_values.get("plans")
            print(json.dumps(plans, indent=2, default=str))

if __name__ == "__main__":
    asyncio.run(main())
