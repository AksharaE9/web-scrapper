"""N9 QualityCritic — routes back to N6 for borderline entities or on to N10."""
from __future__ import annotations
from typing import Any
from app.graph.runtime import node
from app.graph.state import RunState


@node("n9_critic", critical=True, max_retries=0)
async def run(state: RunState) -> dict[str, Any]:
    # Increment iteration counter (routing logic is in build.py _route_critic)
    return {"iteration": state.get("iteration", 0) + 1}
