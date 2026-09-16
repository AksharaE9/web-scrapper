"""N3d — AllThePlacesAgent (optional, brand/chain keywords only)."""
from __future__ import annotations
from typing import Any
from app.graph.runtime import node
from app.graph.state import RunState


@node("n3d_alltheplaces", critical=False, max_retries=1)
async def run(state: RunState) -> dict[str, Any]:

    return {"candidates": [], "source_stats": {"alltheplaces": {"count": 0, "status": "stub"}}}
