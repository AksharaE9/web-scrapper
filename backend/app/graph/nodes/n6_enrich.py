"""Stub nodes N6-N12 — full implementation in Phases 4-6."""
from __future__ import annotations
from typing import Any
from app.graph.runtime import node
from app.graph.state import RunState


@node("n6_enrich", critical=False, max_retries=2)
async def run(state: RunState) -> dict[str, Any]:
    """N6 WebsiteEnrichmentAgent — Phase 5 implementation."""
    return {"entities": state.get("entities", [])}
