"""N9 QualityCritic — Evaluates entity confidence and flags borderline leads for secondary enrichment."""
from __future__ import annotations

import logging
from typing import Any
from app.graph.runtime import node
from app.graph.state import ResolvedEntity, RunState

logger = logging.getLogger(__name__)


@node("n9_critic", critical=True, max_retries=0)
async def run(state: RunState) -> dict[str, Any]:
    iteration = state.get("iteration", 0)
    entities: list[ResolvedEntity] = state.get("entities", [])

    # Find borderline entities that would benefit from secondary crawl
    borderline = [
        e for e in entities
        if 0.40 <= e.confidence < 0.70 and (e.website_url or e.website_domain) and not e.phones_e164
    ]

    logger.info(
        f"N9 QualityCritic (iter {iteration}): total_entities={len(entities)}, "
        f"borderline_uncontacted={len(borderline)}"
    )

    return {
        "iteration": iteration + 1,
        "critic_notes": {
            "iteration": iteration + 1,
            "borderline_count": len(borderline),
        },
    }
