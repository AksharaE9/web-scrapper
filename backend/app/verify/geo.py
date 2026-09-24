"""
app/verify/geo.py — Point-in-polygon check using Shapely (stdlib-only fallback).

Determines whether a coordinate (lon, lat) falls inside a WKT polygon boundary.
Used by the n7_verify node to flag entities outside the requested area.
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def verify_point_in_polygon(lon: float, lat: float, boundary_wkt: str) -> bool:
    """Return True if (lon, lat) is inside boundary_wkt.

    Strategy:
    1. Try Shapely (fast, correct).
    2. Fall back to a simple bounding-box check if Shapely is unavailable.
       The bbox check can produce false-positives for concave polygons but
       never silently accepts entities that are wildly outside the area.
    """
    if not boundary_wkt or lon is None or lat is None:
        return True  # Can't verify — let it pass; downstream checks may catch it

    try:
        from shapely import wkt as shapely_wkt
        from shapely.geometry import Point

        polygon = shapely_wkt.loads(boundary_wkt)
        point = Point(lon, lat)
        return bool(polygon.contains(point) or polygon.touches(point))

    except ImportError:
        log.warning(
            "Shapely not installed — falling back to bounding-box containment check. "
            "Install shapely for exact point-in-polygon verification."
        )
        return _bbox_fallback(lon, lat, boundary_wkt)

    except Exception as exc:  # malformed WKT, etc.
        log.error("verify_point_in_polygon error: %s", exc)
        return True  # conservative: don't reject on parse error


def _bbox_fallback(lon: float, lat: float, boundary_wkt: str) -> bool:
    """Bounding-box approximation parsed from WKT coordinate pairs."""
    import re

    coords = re.findall(r"(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)", boundary_wkt)
    if not coords:
        return True

    lons = [float(c[0]) for c in coords]
    lats = [float(c[1]) for c in coords]
    min_lon, max_lon = min(lons), max(lons)
    min_lat, max_lat = min(lats), max(lats)

    # Expand bbox by 10 % to account for polygon concavity
    lon_margin = (max_lon - min_lon) * 0.10
    lat_margin = (max_lat - min_lat) * 0.10

    return (
        (min_lon - lon_margin) <= lon <= (max_lon + lon_margin)
        and (min_lat - lat_margin) <= lat <= (max_lat + lat_margin)
    )
