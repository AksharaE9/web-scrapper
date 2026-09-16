"""
N11 — Evaluator Agent

Computes run quality metrics:
1. Tier distribution (Verified, Likely, Unverified)
2. Field completeness rates (% phone, % email, % website, % address, % category)
3. Source agreement matrix & overlap
4. Lincoln-Petersen capture-recapture estimated total population:
   N_hat = ((n1 + 1) * (n2 + 1) / (m + 1)) - 1
5. Overall estimated precision/confidence summary
"""

from __future__ import annotations

import logging
from typing import Any

from app.graph.runtime import node
from app.graph.state import ResolvedEntity, RunState

logger = logging.getLogger(__name__)


@node("n11_eval", critical=False, max_retries=1)
async def run(state: RunState) -> dict[str, Any]:
    entities: list[ResolvedEntity] = state.get("entities", [])
    total = len(entities)

    if total == 0:
        logger.info("N11: 0 entities to evaluate.")
        metrics = {
            "total_entities": 0,
            "tier_distribution": {"Verified": 0, "Likely": 0, "Unverified": 0},
            "completeness": {"phone": 0.0, "email": 0.0, "website": 0.0, "address": 0.0},
            "capture_recapture": None,
            "average_confidence": 0.0,
        }
        return {"metrics": metrics}

    # 1. Tier counts
    tiers = {"Verified": 0, "Likely": 0, "Unverified": 0}
    for e in entities:
        t = e.tier if e.tier in tiers else "Unverified"
        tiers[t] += 1

    # 2. Completeness
    with_phone = sum(1 for e in entities if e.phones_e164)
    with_email = sum(1 for e in entities if e.emails)
    with_website = sum(1 for e in entities if e.website_url or e.website_domain)
    with_address = sum(1 for e in entities if e.address_text or e.locality)

    completeness = {
        "phone_rate": round(with_phone / total, 3),
        "email_rate": round(with_email / total, 3),
        "website_rate": round(with_website / total, 3),
        "address_rate": round(with_address / total, 3),
    }

    # 3. Source Overlap & Lincoln-Petersen Capture-Recapture
    overture_entities = {e.id for e in entities if any(s.startswith("overture:") for s in e.source_ids)}
    osm_entities = {e.id for e in entities if any(s.startswith("osm:") for s in e.source_ids)}
    overlap = overture_entities & osm_entities

    n1 = len(overture_entities)
    n2 = len(osm_entities)
    m = len(overlap)

    capture_recapture = None
    if n1 > 0 and n2 > 0:
        # Chapman estimator (unbiased variant of Lincoln-Petersen)
        n_hat = int(((n1 + 1) * (n2 + 1) / (m + 1)) - 1)
        estimated_coverage = round(total / max(n_hat, total), 3) if n_hat > 0 else 1.0
        capture_recapture = {
            "overture_count": n1,
            "osm_count": n2,
            "overlap_count": m,
            "estimated_total_population": max(n_hat, total),
            "estimated_coverage_rate": min(1.0, estimated_coverage),
            "caveat": "Assumes independence between Overture and OSM data collection.",
        }

    # 4. Average confidence
    avg_conf = round(sum(e.confidence for e in entities) / total, 3)

    metrics = {
        "total_entities": total,
        "tier_distribution": tiers,
        "completeness": completeness,
        "capture_recapture": capture_recapture,
        "average_confidence": avg_conf,
        "multi_source_count": sum(1 for e in entities if e.independent_source_count >= 2),
    }

    logger.info(f"N11: Evaluation metrics computed: {metrics}")
    return {"metrics": metrics}
