"""
app/resolve/blocking.py — Blocking keys (Geohash-7 + 8 neighbours, phone, domain) for scalable ER.
app/resolve/lineage.py — Independent source lineage tracker.
"""

from __future__ import annotations

import pygeohash as pgh


def get_blocking_geohashes(lat: float, lon: float, precision: int = 7) -> list[str]:
    """Compute central Geohash and all 8 adjacent bounding neighbours (full k=1 gridDisk)."""
    try:
        center = pgh.encode(lat, lon, precision=precision)
        all_hashes = {center}
        # Orthogonal neighbours
        top = pgh.get_adjacent(center, "top")
        bottom = pgh.get_adjacent(center, "bottom")
        left = pgh.get_adjacent(center, "left")
        right = pgh.get_adjacent(center, "right")
        all_hashes.update([top, bottom, left, right])
        # Diagonal / corner neighbours (completes k=1 9-cell gridDisk)
        all_hashes.add(pgh.get_adjacent(top, "left"))
        all_hashes.add(pgh.get_adjacent(top, "right"))
        all_hashes.add(pgh.get_adjacent(bottom, "left"))
        all_hashes.add(pgh.get_adjacent(bottom, "right"))
        return sorted(list(all_hashes))
    except Exception:
        return []


def is_independent_lineage(source_a: str, source_b: str) -> bool:
    """
    Check if two data sources represent independent corroborating datasets.
    Overture Places (Meta/Microsoft/Foursquare) and OpenStreetMap are independent.
    """
    s_a = source_a.lower()
    s_b = source_b.lower()
    if s_a == s_b:
        return False
    if "overture" in s_a and "osm" in s_b:
        return True
    if "osm" in s_a and "overture" in s_b:
        return True
    return True
