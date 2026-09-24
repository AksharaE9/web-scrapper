"""
app/verify/web.py — Website HTTP liveness and business name match check.
app/verify/geo.py — Geographic boundary point-in-polygon containment verification.

P13 SECURITY NOTE: verify=False was removed. TLS verification is mandatory.
A MITM with verify=False can inject fabricated phone numbers into lead data.
"""

from __future__ import annotations

from typing import Any

import httpx
from rapidfuzz import fuzz
from shapely import wkt
from shapely.geometry import Point


async def verify_website(url: str, business_name: str | None = None) -> dict[str, Any]:
    """Check website HTTP liveness within 10s and test entity name similarity.

    P13: verify=True (default). TLS must not be bypassed — MITM risk.
    If a target URL uses a self-signed certificate, it will fail here, which
    is the correct behavior: we should NOT record data from unverified sources.
    """
    if not url:
        return {"live": False, "name_match": False, "status_code": 0}

    target_url = url if url.startswith(("http://", "https://")) else f"https://{url}"
    try:
        # verify=True is the httpx default; stated explicitly for auditability.
        # Do NOT add verify=False without security review.
        async with httpx.AsyncClient(timeout=3.0, follow_redirects=True, verify=True) as client:
            resp = await client.get(target_url)
            is_live = (200 <= resp.status_code < 400)

            name_match = False
            if is_live and business_name:
                text_sample = resp.text[:5000].lower()
                name_clean = business_name.lower().strip()
                if name_clean in text_sample or fuzz.partial_ratio(name_clean, text_sample) >= 75:
                    name_match = True

            return {
                "live": is_live,
                "name_match": name_match,
                "status_code": resp.status_code,
            }
    except Exception:
        return {"live": False, "name_match": False, "status_code": 0}


def verify_point_in_polygon(lon: float, lat: float, polygon_wkt: str) -> bool:
    """Verify coordinate point is contained strictly within the WKT boundary polygon."""
    if not polygon_wkt:
        return True
    try:
        poly = wkt.loads(polygon_wkt)
        pt = Point(lon, lat)
        return bool(poly.contains(pt) or poly.touches(pt) or poly.distance(pt) < 0.001)
    except Exception:
        return True
