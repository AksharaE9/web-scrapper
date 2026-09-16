"""
Import seeds script — populates `area_seeds` and `keyword_presets` tables from JSON files.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

# Ensure backend root is on sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

if sys.platform == "win32" and sys.version_info < (3, 14):
    try:
        _set_policy = getattr(asyncio, "set_event_loop_policy", None)
        _selector_policy = getattr(asyncio, "WindowsSelectorEventLoopPolicy", None)
        if _set_policy and _selector_policy:
            _set_policy(_selector_policy())
    except Exception:
        pass

from app.db.pool import get_pool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("import_seeds")

SEEDS_DIR = BACKEND_DIR / "seeds"


async def main() -> None:
    pool = get_pool()

    # 1. Import Keyword Presets
    presets_file = SEEDS_DIR / "keyword_presets.json"
    if presets_file.exists():
        with open(presets_file, "r", encoding="utf-8") as f:
            presets_data = json.load(f)

        async with pool.connection() as conn:
            for p in presets_data:
                await conn.execute(
                    """
                    INSERT INTO keyword_presets (name, search_categories, exclude_keywords)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (name) DO UPDATE SET
                        search_categories = EXCLUDED.search_categories,
                        exclude_keywords = EXCLUDED.exclude_keywords
                    """,
                    (p["name"], p["search_categories"], p.get("exclude_keywords", [])),
                )
        logger.info(f"Imported {len(presets_data)} keyword presets.")

    # 2. Import Area Seeds
    areas_file = SEEDS_DIR / "areas.json"
    if areas_file.exists():
        with open(areas_file, "r", encoding="utf-8") as f:
            cities_data = json.load(f)

        count = 0
        async with pool.connection() as conn:
            for city_obj in cities_data:
                city = city_obj["city"]
                state = city_obj["state"]
                country = city_obj["country"]
                for area in city_obj["areas"]:
                    locality = area["locality"]
                    pincode = area.get("pincode")
                    lon, lat = area["centroid"]
                    min_lon, min_lat, max_lon, max_lat = area["bbox"]

                    # PostGIS polygon for bounding box
                    poly_wkt = f"POLYGON(({min_lon} {min_lat}, {max_lon} {min_lat}, {max_lon} {max_lat}, {min_lon} {max_lat}, {min_lon} {min_lat}))"

                    await conn.execute(
                        """
                        INSERT INTO area_seeds (
                            locality, city, state, country, pincode, geom, boundary_polygon
                        ) VALUES (
                            %s, %s, %s, %s, %s,
                            ST_SetSRID(ST_MakePoint(%s, %s), 4326),
                            ST_GeomFromText(%s, 4326)
                        )
                        ON CONFLICT (locality, city) DO UPDATE SET
                            pincode = EXCLUDED.pincode,
                            geom = EXCLUDED.geom,
                            boundary_polygon = EXCLUDED.boundary_polygon
                        """,
                        (locality, city, state, country, pincode, lon, lat, poly_wkt),
                    )
                    count += 1
        logger.info(f"Imported {count} area seeds across {len(cities_data)} cities.")


if __name__ == "__main__":
    asyncio.run(main())
