"""N7 VerificationAgent — Multi-criteria integrity and validity checks."""
from __future__ import annotations

import asyncio
from typing import Any

from app.graph.runtime import node
from app.graph.state import CheckResult, ResolvedEntity, RunState
from app.verify.checks import run_entity_verification_checks


@node("n7_verify", critical=False, max_retries=0)
async def run(state: RunState) -> dict[str, Any]:
    entities: list[ResolvedEntity] = state.get("entities", [])
    geo = state.get("geo")
    boundary_wkt = geo.polygon_wkt if geo else None
    
    query = state.get("query")
    target_locality = query.location.locality if query and query.location else None
    target_city = query.location.city if query and query.location else None

    verifications: dict[str, list[CheckResult]] = {}

    # Process in batches with high concurrency for fast DNS & web checks
    semaphore = asyncio.Semaphore(25)

    async def _verify_one(entity: ResolvedEntity) -> tuple[str, list[CheckResult]]:
        async with semaphore:
            checks = await run_entity_verification_checks(
                entity=entity,
                boundary_wkt=boundary_wkt,
                target_locality=target_locality,
                target_city=target_city,
            )
            return entity.id, checks

    tasks = [_verify_one(e) for e in entities]
    results = await asyncio.gather(*tasks, return_exceptions=False)

    for ent_id, checks in results:
        verifications[ent_id] = checks

    return {"verifications": verifications}

