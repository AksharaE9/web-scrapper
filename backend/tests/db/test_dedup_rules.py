"""
tests/db/test_dedup_rules.py — Database deduplication assertions against live PostGIS.
"""

from __future__ import annotations

import uuid
import pytest
from app.db import pool as db_pool


@pytest.mark.asyncio
async def test_spatial_proximity_and_name_dedup() -> None:
    """Businesses within 50m with matching name should be identified as neighbors."""
    async with db_pool.get_conn() as conn:
        biz1_id = str(uuid.uuid4())
        # Point 1 in Whitefield: lon 77.7499, lat 12.9698
        await conn.execute(
            """
            INSERT INTO businesses (id, canonical_name, name_norm, geom, confidence, tier)
            VALUES (%s, 'Sri Lakshmi Pooja Stores', 'sri lakshmi pooja stores',
                    ST_SetSRID(ST_MakePoint(77.7499, 12.9698), 4326)::geography, 0.85, 'Verified')
            """,
            (biz1_id,),
        )

        # Point 2 roughly 20m away: lon 77.7500, lat 12.9699
        cur = await conn.execute(
            """
            SELECT id, canonical_name
            FROM businesses
            WHERE ST_DWithin(geom, ST_SetSRID(ST_MakePoint(77.7500, 12.9699), 4326)::geography, 50)
            """,
        )
        neighbors = await cur.fetchall()
        assert len(neighbors) >= 1
        found_ids = [str(n["id"]) if isinstance(n, dict) else str(n[0]) for n in neighbors]
        assert biz1_id in found_ids


@pytest.mark.asyncio
async def test_distinct_businesses_far_apart_not_deduped() -> None:
    """Same name 5km away must not be matched as a 50m neighbor."""
    async with db_pool.get_conn() as conn:
        biz_id = str(uuid.uuid4())
        # Point in Koramangala: lon 77.6245, lat 12.9352
        await conn.execute(
            """
            INSERT INTO businesses (id, canonical_name, name_norm, geom, confidence, tier)
            VALUES (%s, 'Far Away Pooja Stores', 'far away pooja stores',
                    ST_SetSRID(ST_MakePoint(77.6245, 12.9352), 4326)::geography, 0.80, 'Verified')
            """,
            (biz_id,),
        )

        # Query in Whitefield (15km away)
        cur = await conn.execute(
            """
            SELECT id
            FROM businesses
            WHERE id = %s AND ST_DWithin(geom, ST_SetSRID(ST_MakePoint(77.7499, 12.9698), 4326)::geography, 50)
            """,
            (biz_id,),
        )
        res = await cur.fetchall()
        assert len(res) == 0, "Businesses 15km apart must not be returned in 50m neighborhood query"
