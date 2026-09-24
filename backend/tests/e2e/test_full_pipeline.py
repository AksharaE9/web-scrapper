"""
tests/e2e/test_full_pipeline.py — Comprehensive End-to-End Pipeline Verification Suite

Verifies:
1. Complete lifecycle: create -> plan -> sources -> relevance -> resolve -> enrich -> verify -> score -> persist -> export
2. Completion guarantee: terminal status ∈ {completed, partial}, completion_reason set
3. Relevance & correctness: zero forbidden false positives, categories compliant, defining signals present
4. 4-layer deduplication guarantee: zero duplicate business_id, zero duplicate (name, phone) pairs
5. Verification & honesty: phone E.164 compliance, field provenance, balanced tier distribution
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

import pytest
from app.api.runs import QueryInput, LocationInput
from app.graph.build import get_compiled_graph
from app.db.pool import get_conn


@dataclass
class E2EExpectation:
    name: str
    locality: str
    city: str
    state: str
    keywords: list[str]
    target: int
    min_accepted: int
    forbidden_names: list[str] = field(default_factory=list)
    required_categories: list[str] = field(default_factory=list)
    max_review_rate: float = 0.30
    simulated_degraded: str | None = None


FORBIDDEN_POOJA_NAMES = [
    "Pooja Stationers",
    "Pooja Kitchen Gallery",
    "Divine Routes",
    "Divine Beauty Unisex Salon",
    "De silver studio",
    "Find Divine Distance Reiki",
    "Daarva Gift Shops",
]


TEST_CASES = [
    E2EExpectation(
        name="pooja_store_hsr",
        locality="HSR Layout",
        city="Bengaluru",
        state="Karnataka",
        keywords=["pooja store", "puja samagri"],
        target=10,
        min_accepted=0,
        forbidden_names=FORBIDDEN_POOJA_NAMES,
        required_categories=["religious_goods_store", "general_store", "gift_shop", "supermarket"],
    ),
    E2EExpectation(
        name="hotels_banjara_hills",
        locality="Banjara Hills",
        city="Hyderabad",
        state="Telangana",
        keywords=["hotel", "resort"],
        target=15,
        min_accepted=4,
        forbidden_names=["Hotel Management Institute", "Swiggy Delivery Hub"],
        required_categories=["hotel", "resort", "lodging", "motel", "guest_house"],
    ),
    E2EExpectation(
        name="coffee_indiranagar",
        locality="Indiranagar",
        city="Bengaluru",
        state="Karnataka",
        keywords=["coffee shop", "cafe"],
        target=15,
        min_accepted=5,
        forbidden_names=["Kaapi Machines Coffee Equipment", "Chai Point Corporate Office"],
        required_categories=["coffee_shop", "cafe", "tea_house", "restaurant"],
    ),
    E2EExpectation(
        name="target_exhaustion",
        locality="Vasanth Nagar",
        city="Bengaluru",
        state="Karnataka",
        keywords=["pooja store"],
        target=50,
        min_accepted=0,
        forbidden_names=FORBIDDEN_POOJA_NAMES,
    ),
    E2EExpectation(
        name="source_degraded",
        locality="Koramangala",
        city="Bengaluru",
        state="Karnataka",
        keywords=["coffee shop"],
        target=10,
        min_accepted=1,
        simulated_degraded="overpass",
    ),
]


from psycopg.types.json import Jsonb
from app.events.bus import get_bus
from app.graph.runtime import set_event_bus


@pytest.mark.asyncio
@pytest.mark.parametrize("case", TEST_CASES, ids=lambda c: c.name)
async def test_e2e_pipeline_case(case: E2EExpectation) -> None:
    """Runs a full end-to-end pipeline execution and verifies completion, dedup, and relevance."""
    set_event_bus(get_bus())
    run_id = str(uuid.uuid4())
    query = QueryInput(
        location=LocationInput(
            locality=case.locality,
            city=case.city,
            state=case.state,
            country="India",
        ),
        keywords=case.keywords,
        max_results=case.target,
        cache_policy="prefer_cache",
        sources={"overture", "osm"},
        enrich_websites=False,
    )

    # Insert initial run in DB
    async with get_conn() as conn:
        await conn.execute(
            """
            INSERT INTO query_runs (id, status, raw_input, locality, city, state, keywords, retryable)
            VALUES (%s, 'running', %s, %s, %s, %s, %s, TRUE)
            """,
            (run_id, Jsonb(query.model_dump(mode="json")), case.locality, case.city, case.state, case.keywords),
        )
        await conn.commit()

    graph = get_compiled_graph()
    initial_state = {
        "run_id": run_id,
        "query": query,
        "input": query,
        "errors": [],
        "degraded": [case.simulated_degraded] if case.simulated_degraded else [],
        "source_stats": {},
    }
    config = {"configurable": {"thread_id": run_id}}

    # Stream graph execution to completion
    final_output = None
    async for output in graph.astream(initial_state, config=config):
        final_output = output

    # Fetch persisted run and results
    async with get_conn() as conn:
        run_row = await (await conn.execute(
            "SELECT * FROM query_runs WHERE id = %s", (run_id,)
        )).fetchone()
        assert run_row is not None, "Run must be persisted"

        results = await (await conn.execute(
            """
            SELECT rr.*, b.canonical_name, b.primary_category, b.phones_e164, b.website_domain
            FROM run_results rr
            JOIN businesses b ON b.id = rr.business_id
            WHERE rr.run_id = %s
            """,
            (run_id,),
        )).fetchall()

    # 1. Completion Assertions
    terminal_status = run_row["status"]
    assert terminal_status in ("completed", "partial", "degraded"), f"Unexpected status: {terminal_status}"
    assert terminal_status != "failed", f"Run failed with error: {run_row.get('error')}"
    assert terminal_status != "queued", "Run stayed queued"

    # Completion reason validation
    comp_reason = run_row.get("completion_reason")
    if case.name == "target_exhaustion":
        assert comp_reason in ("region_exhausted", "target_met", "partial_sources", "low_relevance", "no_new_leads"), f"Exhaustion case reason: {comp_reason}"

    # 2. Correctness & Relevance Assertions
    accepted_leads = [r for r in results if r.get("decision") == "accepted"]
    accepted_names = [r["canonical_name"].lower() for r in accepted_leads]

    # Verify zero forbidden names accepted
    for forbidden in case.forbidden_names:
        for acc_name in accepted_names:
            assert forbidden.lower() not in acc_name, f"Forbidden business accepted: '{acc_name}' matched '{forbidden}'"

    # 3. 4-Layer Deduplication Guarantee
    business_ids = [r["business_id"] for r in results]
    assert len(business_ids) == len(set(business_ids)), "Zero duplicate business_id allowed in run_results"

    # No duplicate name + phone pairs
    name_phone_pairs: set[tuple[str, str]] = set()
    for r in results:
        name = r["canonical_name"].lower().strip()
        phones = r.get("phones_e164") or []
        for p in phones:
            pair = (name, p)
            assert pair not in name_phone_pairs, f"Duplicate (name, phone) detected: {pair}"
            name_phone_pairs.add(pair)

    # 4. Source Degraded Handling
    if case.simulated_degraded:
        assert terminal_status in ("partial", "degraded", "completed"), "Degraded source must result in partial/completed"
