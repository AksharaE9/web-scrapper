"""
app/sources/overpass.py — OpenStreetMap Overpass API client with failover and rate limiting.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any
import httpx
from app.settings import settings

logger = logging.getLogger(__name__)


def build_overpass_query(osm_tag_filters: list[str], bbox: tuple[float, float, float, float], timeout: int = 25) -> str:
    """
    Build Overpass QL query over given bounding box: (min_lon, min_lat, max_lon, max_lat).
    Overpass bbox format: (min_lat, min_lon, max_lat, max_lon).
    """
    min_lon, min_lat, max_lon, max_lat = bbox
    bbox_str = f"{min_lat},{min_lon},{max_lat},{max_lon}"

    filter_blocks: list[str] = []
    for tag in osm_tag_filters:
        if "=" in tag:
            k, _, v = tag.partition("=")
            filter_blocks.append(f'nwr["{k}"="{v}"]({bbox_str});')
        else:
            filter_blocks.append(f'nwr["{tag}"]({bbox_str});')

    if not filter_blocks:
        filter_blocks = [f'nwr["shop"]({bbox_str});', f'nwr["amenity"]({bbox_str});']

    body = "\n  ".join(filter_blocks)
    return f"""[out:json][timeout:{timeout}];
(
  {body}
);
out center body;
>;
out skel qt;
"""


async def execute_overpass_query(query: str) -> dict[str, Any]:
    """Execute Overpass query with automatic endpoint failover."""
    headers = {"User-Agent": settings.crawler_user_agent}
    last_err: Exception | None = None

    for ep in settings.overpass_endpoints:
        try:
            async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
                resp = await client.post(ep, data={"data": query})
                if resp.status_code == 200:
                    return resp.json()
                elif resp.status_code in (429, 504):
                    logger.warning(f"Overpass endpoint {ep} returned {resp.status_code}, trying next endpoint")
                    await asyncio.sleep(1.0)
                    continue
        except Exception as e:
            last_err = e
            logger.warning(f"Overpass endpoint {ep} failed: {e}")
            continue

    raise RuntimeError(f"All Overpass endpoints failed: {last_err}")
