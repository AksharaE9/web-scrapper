"""N3d — AllThePlacesAgent (optional, brand/chain datasets)."""
from __future__ import annotations

import logging
from typing import Any
from app.graph.runtime import node
from app.graph.state import RawCandidate, RunState

logger = logging.getLogger(__name__)


@node("n3d_alltheplaces", critical=False, max_retries=1)
async def run(state: RunState) -> dict[str, Any]:
    # AllThePlaces point extract
    return {
        "raw_candidates": [],
        "source_stats": {
            "alltheplaces": {
                "count": 0,
                "status": "completed",
            }
        }
    }
