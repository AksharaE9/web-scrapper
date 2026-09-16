"""N8 ConfidenceScorer — Multi-source verification scoring and tier assignment."""
from __future__ import annotations

from typing import Any

from app.graph.runtime import node
from app.graph.state import ResolvedEntity, RunState


@node("n8_score", critical=True, max_retries=0)
async def run(state: RunState) -> dict[str, Any]:
    entities: list[ResolvedEntity] = state.get("entities", [])
    verifications = state.get("verifications", {})

    scored = []
    for entity in entities:
        checks = verifications.get(entity.id, [])
        passed_check_names = {c.check_name for c in checks if c.outcome == "passed"}

        score = 0.45  # baseline for geographically bounded and resolved POI

        if entity.phones_e164:
            score += 0.25
        if entity.website_url or entity.website_domain:
            score += 0.15
        if entity.emails:
            score += 0.10
        if entity.independent_source_count >= 2:
            score += 0.20
        if entity.address_text or (entity.locality and entity.city):
            score += 0.10
        if "category_provenance" in passed_check_names:
            score += 0.05

        score = min(0.99, score)

        # Tier assignment
        # Verified: high confidence with verified phone, website, or multi-source agreement
        if score >= 0.70 or (entity.phones_e164 and entity.website_url) or entity.independent_source_count >= 2:
            tier = "Verified"
        elif score >= 0.50 or entity.phones_e164 or entity.website_url or entity.address_text:
            tier = "Likely"
        else:
            tier = "Unverified"

        scored.append(entity.model_copy(update={"confidence": round(score, 3), "tier": tier}))

    # Sort entities radiating outwards from the locality center:
    # Ring 0 (<1.5km), Ring 1 (1.5-3.5km), Ring 2 (3.5-6km), Ring 3 (>6km)
    # Inside each ring, rank by confidence descending, then distance ascending
    def _rank_key(e: ResolvedEntity) -> tuple[int, float, float]:
        d = e.distance_m if e.distance_m is not None else 99999.0
        if d <= 1500:
            ring = 0
        elif d <= 3500:
            ring = 1
        elif d <= 6000:
            ring = 2
        else:
            ring = 3
        # Negative confidence so highest confidence is first
        return (ring, -e.confidence, d)

    sorted_entities = sorted(scored, key=_rank_key)

    return {"entities": sorted_entities}
