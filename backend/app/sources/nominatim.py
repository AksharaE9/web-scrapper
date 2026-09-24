"""
app/sources/nominatim.py — Rate-limited Nominatim geocoding client with in-memory cache.
Complies strictly with OSMF Nominatim Usage Policy (max 1 req/s, identifying User-Agent).
"""

from __future__ import annotations

import asyncio
import time
from typing import Any
import httpx
import structlog

from app.settings import settings

log = structlog.get_logger()

# In-memory cache for geocoded queries within the process lifetime
_GEO_CACHE: dict[str, dict[str, Any]] = {}
_LAST_REQUEST_TIME: float = 0.0
_LOCK = asyncio.Lock()


async def geocode(query: str) -> dict[str, Any] | None:
    """Geocode a text query via Nominatim with strict 1 req/s rate-limiting."""
    global _LAST_REQUEST_TIME
    q_norm = query.strip().lower()
    if q_norm in _GEO_CACHE:
        return _GEO_CACHE[q_norm]

    headers = {
        "User-Agent": f"{settings.crawler_user_agent} (contact: {settings.contact_email})",
        "Referer": "https://leadcorezero.io",
    }

    async with _LOCK:
        elapsed = time.monotonic() - _LAST_REQUEST_TIME
        if elapsed < 1.1:
            await asyncio.sleep(1.1 - elapsed)

        params = {
            "q": query,
            "format": "jsonv2",
            "polygon_geojson": 1,
            "addressdetails": 1,
            "limit": 5,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
                resp = await client.get(f"{settings.nominatim_url}/search", params=params)
                _LAST_REQUEST_TIME = time.monotonic()
                if resp.status_code == 200:
                    data = resp.json()
                    if data and isinstance(data, list):
                        res = data[0]
                        _GEO_CACHE[q_norm] = res
                        return res
                elif resp.status_code == 429:
                    log.warning("Nominatim rate-limit hit (429), backing off", query=query)
                    await asyncio.sleep(5.0)
        except Exception as e:
            log.warning("Nominatim geocoding request failed", query=query, error=str(e))

    return None
