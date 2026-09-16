"""
N4 — CandidateFilter

Filters raw candidates:
  1. Point-in-polygon check (Shapely) — keeps candidates inside the boundary
     or within 150m of the boundary edge (edge_case=True)
  2. Keyword match score ≥ threshold
  3. Exclude patterns (name/category)
  4. operating_status != permanently_closed
"""

from __future__ import annotations

import re
from typing import Any

import pygeohash
import shapely.wkt
from shapely.geometry import Point

from app.graph.runtime import node
from app.graph.state import GeoResolution, KeywordPlan, RawCandidate, RunState

EDGE_CASE_BUFFER_DEG = 150 / 111_000  # 150m in degrees


def _match_score(
    candidate: RawCandidate,
    plans: list[KeywordPlan],
) -> tuple[float, str, bool]:
    """Return (score, reason, is_excluded)."""
    name_lower = candidate.name.lower()
    cats_lower = [c.lower() for c in candidate.categories]

    best_score = 0.0
    best_reason = ""

    for plan in plans:
        # Exclude patterns check
        for ex_pat in plan.exclude_patterns:
            if re.search(ex_pat, name_lower, re.IGNORECASE):
                return 0.0, f"excluded:{ex_pat}", True

        # Category match (strong = 0.9)
        for cat in plan.overture_basic_categories + plan.overture_taxonomy_paths:
            if any(cat.lower() in c for c in cats_lower):
                if 0.9 > best_score:
                    best_score = 0.9
                    best_reason = f"category:{cat}"

        # OSM tag match (strong = 0.85)
        for tag in plan.osm_tag_filters:
            k, _, v = tag.partition("=")
            if any(k.lower() in c or v.lower() in c for c in cats_lower):
                if 0.85 > best_score:
                    best_score = 0.85
                    best_reason = f"osm_tag:{tag}"

        # Name pattern match (medium = 0.7)
        for pattern in plan.name_patterns:
            if re.search(pattern, name_lower, re.IGNORECASE):
                if 0.7 > best_score:
                    best_score = 0.7
                    best_reason = f"name_pattern:{pattern}"

        # Synonym in name (weak = 0.5)
        for syn in plan.synonyms:
            if syn.lower() in name_lower:
                if 0.5 > best_score:
                    best_score = 0.5
                    best_reason = f"synonym:{syn}"

    return best_score, best_reason, False


@node("n4_filter", critical=True, max_retries=0)
async def run(state: RunState) -> dict[str, Any]:
    geo: GeoResolution | None = state.get("geo")
    plans: list[KeywordPlan] = state.get("plans", [])
    candidates: list[RawCandidate] = state.get("candidates", [])
    run_id = state["run_id"]

    if not geo:
        return {"candidates": []}

    boundary = shapely.wkt.loads(geo.polygon_wkt)
    buffered = boundary.buffer(EDGE_CASE_BUFFER_DEG)

    passed: list[RawCandidate] = []
    rejected: list[dict[str, Any]] = []

    for c in candidates:
        # Operating status filter
        if c.operating_status == "permanently_closed":
            rejected.append({
                "run_id": run_id, "source": c.source,
                "source_record_id": c.source_record_id,
                "name": c.name, "reason": "permanently_closed",
            })
            continue

        # Point-in-polygon
        pt = Point(c.lon, c.lat)
        inside = boundary.contains(pt)
        edge = not inside and buffered.contains(pt)

        if not inside and not edge:
            rejected.append({
                "run_id": run_id, "source": c.source,
                "source_record_id": c.source_record_id,
                "name": c.name, "reason": "outside_boundary",
            })
            continue

        # Keyword match
        score, reason, is_excluded = _match_score(c, plans)
        if is_excluded:
            rejected.append({
                "run_id": run_id, "source": c.source,
                "source_record_id": c.source_record_id,
                "name": c.name, "reason": f"excluded:{reason}",
            })
            continue

        if score < 0.4:
            rejected.append({
                "run_id": run_id, "source": c.source,
                "source_record_id": c.source_record_id,
                "name": c.name, "reason": f"low_score:{score:.2f}",
            })
            continue

        passed.append(c)

    # Bulk insert rejected candidates
    if rejected:
        from app.db.pool import get_conn
        async with get_conn() as conn:
            for r in rejected:
                await conn.execute(
                    "INSERT INTO rejected_candidates (run_id, source, source_record_id, name, reason) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (r["run_id"], r["source"], r["source_record_id"], r["name"], r["reason"]),
                )
            await conn.commit()

    # Add geohash7 to passed candidates for downstream blocking
    for c in passed:
        c.raw["geohash7"] = pygeohash.encode(c.lat, c.lon, precision=7)

    return {
        "candidates": passed,
        "source_stats": {
            "filter": {"passed": len(passed), "rejected": len(rejected)}
        },
    }
