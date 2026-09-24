"""
Seed Importer Script — LeadCore Zero

Reads seeds/areas.json and populates the area_seeds table in PostgreSQL with PostGIS geometries.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from app.db.pool import close_pools, get_conn, init_pools

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("import_seeds")

SEEDS_FILE = Path(__file__).resolve().parent.parent / "seeds" / "areas.json"


async def import_seeds() -> None:
    if not SEEDS_FILE.exists():
        logger.error(f"Seed file not found: {SEEDS_FILE}")
        return

    logger.info(f"Loading seeds from {SEEDS_FILE}")
    data = json.loads(SEEDS_FILE.read_text(encoding="utf-8"))

    await init_pools()
    imported_count = 0

    try:
        async with get_conn() as conn:
            # Ensure area_seeds table exists
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS area_seeds (
                    id SERIAL PRIMARY KEY,
                    locality VARCHAR(128) NOT NULL,
                    area VARCHAR(128),
                    city VARCHAR(128) NOT NULL,
                    state VARCHAR(128),
                    country VARCHAR(64) DEFAULT 'India',
                    pincode VARCHAR(16),
                    lon DOUBLE PRECISION NOT NULL,
                    lat DOUBLE PRECISION NOT NULL,
                    geom GEOMETRY(Point, 4326),
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    UNIQUE(locality, city, state)
                );
                CREATE INDEX IF NOT EXISTS idx_area_seeds_locality ON area_seeds(locality);
                CREATE INDEX IF NOT EXISTS idx_area_seeds_city ON area_seeds(city);
                """
            )

            for city_group in data:
                city = city_group.get("city")
                state = city_group.get("state")
                country = city_group.get("country", "India")

                for area in city_group.get("areas", []):
                    locality = area.get("locality")
                    pincode = area.get("pincode")
                    centroid = area.get("centroid", [])
                    if len(centroid) < 2:
                        continue
                    lon, lat = centroid[0], centroid[1]

                    await conn.execute(
                        """
                        INSERT INTO area_seeds (locality, area, city, state, country, pincode, lon, lat, geom)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))
                        ON CONFLICT (locality, city, state) DO UPDATE SET
                            pincode = EXCLUDED.pincode,
                            lon = EXCLUDED.lon,
                            lat = EXCLUDED.lat,
                            geom = EXCLUDED.geom;
                        """,
                        (locality, locality, city, state, country, pincode, lon, lat, lon, lat),
                    )
                    imported_count += 1

            await conn.commit()
            logger.info(f"Successfully imported / updated {imported_count} area seeds.")
    finally:
        await close_pools()


if __name__ == "__main__":
    asyncio.run(import_seeds())
