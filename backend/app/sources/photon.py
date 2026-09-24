"""
app/sources/photon.py — Komoot Photon geocoding client for OSM reverse/forward geocoding.
"""

from __future__ import annotations

import logging
from typing import Any
import httpx
from app.settings import settings

logger = logging.getLogger(__name__)


async def geocode_photon(query: str, lat: float | None = None, lon: float | None = None) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"q": query, "limit": 5}
    if lat is not None and lon is not None:
        params["lat"] = lat
        params["lon"] = lon

    headers = {"User-Agent": settings.crawler_user_agent}
    try:
        async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
            resp = await client.get(f"{settings.photon_url}/api", params=params)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("features", [])
    except Exception as e:
        logger.warning(f"Photon geocoding error: {e}")
    return []
