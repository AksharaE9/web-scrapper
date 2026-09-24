"""
LangGraph Pipeline Contract Test Suite

Runs the entire LangGraph pipeline from START to END using MemorySaver,
mocking network boundaries so it runs in < 5 seconds offline.
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langgraph.checkpoint.memory import MemorySaver

from app.graph.build import build_graph
from app.graph.state import (
    Budget,
    LocationInput,
    QueryInput,
    RawCandidate,
    RunState,
)


@pytest.mark.asyncio
async def test_full_pipeline_contract_offline() -> None:
    """End-to-end execution of compiled LangGraph from START to END."""
    # 1. Compile graph with MemorySaver checkpointer
    graph = build_graph()
    app = graph.compile(checkpointer=MemorySaver())

    run_id = str(uuid.uuid4())
    initial_state: RunState = {
        "run_id": run_id,
        "query": QueryInput(
            keywords=["pooja store"],
            location=LocationInput(locality="HSR Layout", city="Bengaluru", state="Karnataka", country="India"),
            sources={"overture", "osm"},
            max_results=10,
            enrich_websites=False,
        ),
        "budget": Budget(max_http_calls=100, max_llm_calls=10),
        "candidates": [],
        "entities": [],
        "verifications": {},
        "errors": [],
        "degraded": [],
        "iteration": 0,
        "source_stats": {},
    }

    mock_overture_candidates = [
        RawCandidate(
            source="overture",
            source_record_id="ov_pooja_1",
            name="Sri Balaji Pooja Store",
            lon=77.641,
            lat=12.915,
            categories=["pooja_store", "religious_goods"],
            phones=["+918025551234"],
            websites=["https://sribalajipooja.com"],
            address={"locality": "HSR Layout", "city": "Bengaluru"},
            source_confidence=0.95,
            raw={"name": "Sri Balaji Pooja Store", "brand": None},
        )
    ]

    mock_osm_candidates = [
        RawCandidate(
            source="osm",
            source_record_id="osm_pooja_2",
            name="Sri Balaji Pooja Store",
            lon=77.6412,
            lat=12.9152,
            categories=["religious_goods"],
            phones=["08025551234"],
            websites=[],
            address={"locality": "HSR Layout", "city": "Bengaluru"},
            source_confidence=0.90,
            raw={"name": "Sri Balaji Pooja Store", "shop": "pooja"},
        )
    ]

    # Patch network sources and database persistence
    with (
        patch("app.graph.nodes.n3a_overture._sync_fetch_overture", return_value=(mock_overture_candidates, {"matched": 1, "raw_count": 1, "release": "test"})),
        patch("app.graph.nodes.n3b_overpass._fetch_nominatim_pois", new=AsyncMock(return_value=mock_osm_candidates)),
        patch("app.graph.nodes.n4_relevance.bulk_insert_rejected_candidates", new=AsyncMock()),
        patch("app.graph.nodes.n4_relevance.get_conn") as mock_n4_conn,
        patch("app.graph.nodes.n10_persist.get_pool") as mock_get_pool,
        patch("app.graph.nodes.n12_report.get_pool") as mock_report_pool,
    ):
        mock_ctx = AsyncMock()
        mock_n4_conn.return_value.__aenter__.return_value = mock_ctx

        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_tx = AsyncMock()
        mock_conn.transaction = MagicMock(return_value=mock_tx)
        mock_cursor = AsyncMock()
        mock_cursor.fetchone.return_value = None
        mock_conn.execute.return_value = mock_cursor
        mock_pool.connection.return_value.__aenter__.return_value = mock_conn

        mock_get_pool.return_value = mock_pool
        mock_report_pool.return_value = mock_pool

        # Execute graph
        config = {"configurable": {"thread_id": run_id}}
        final_state = await app.ainvoke(initial_state, config=config)

    # Assertions on pipeline contract
    assert final_state is not None
    assert "geo" in final_state
    assert final_state["geo"] is not None
    assert final_state["geo"].geo_confidence >= 0.60
    assert "entities" in final_state
    entities = final_state["entities"]
    assert len(entities) >= 1
    golden = entities[0]
    assert "Sri Balaji Pooja Store" in golden.canonical_name
    assert golden.confidence >= 0.50
    assert golden.tier in ("Verified", "Likely", "Unverified")
    assert "metrics" in final_state
