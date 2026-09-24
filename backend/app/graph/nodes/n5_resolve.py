"""
N5 — EntityResolverAgent

Probabilistic entity resolution using Splink (Fellegi-Sunter, EM-trained, DuckDB backend).
Blocking: geohash-7 neighbourhood OR same phone OR same domain.
Golden record selection: highest (source_reliability × recency × agreement).
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog

from app.graph.runtime import node
from app.graph.state import RawCandidate, ResolvedEntity, RunState
from app.resolve.geo_math import haversine_distance_m
from app.resolve.golden_record import build_golden_record
from app.resolve.splink_model import cluster_candidates_probabilistic

log = structlog.get_logger()


@node("n5_resolve", critical=True, max_retries=0)
async def run(state: RunState) -> dict[str, Any]:
    candidates = state.get("candidates", [])
    if not candidates:
        return {"entities": []}

    geo = state.get("geo")
    centroid = geo.centroid if geo else None

    # Probabilistic clustering with blocking
    clusters = cluster_candidates_probabilistic(candidates, match_threshold=0.85)

    entities: list[ResolvedEntity] = []
    for cluster in clusters:
        cluster_id = str(uuid.uuid4())
        entity = build_golden_record(cluster_id, cluster)

        # Calculate centroid distance if available
        if centroid and len(centroid) == 2:
            dist_m = round(haversine_distance_m(entity.lon, entity.lat, centroid[0], centroid[1]), 1)
            entity = entity.model_copy(update={"distance_m": dist_m, "distance_km": round(dist_m / 1000.0, 2)})

        entities.append(entity)

    log.info(
        "Entity resolution complete",
        candidates=len(candidates),
        clusters=len(clusters),
    )

    return {"entities": entities}

