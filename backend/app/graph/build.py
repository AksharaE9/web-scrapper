"""
LangGraph Graph Builder — LeadCore Zero v2

Wires all nodes into a StateGraph with:
  - Send() fan-out for parallel source agents (N3a/b/c/d/e)
  - interrupt() for geo disambiguation (human-in-the-loop)
  - AsyncPostgresSaver checkpointer (direct Neon URL)
  - All edges declared explicitly for docstring/test compatibility
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, cast

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from app.db.pool import get_direct_async_pool
from app.graph.state import GeoResolution, QueryInput, RunState
from app.settings import settings

# Lazy imports to keep startup fast (heavy deps like DuckDB, Splink load on first use)
from app.graph.nodes import (
    n0_input,
    n1_geo,
    n2_keyword,
    n3a_overture,
    n3b_overpass,
    n3c_wikidata,
    n3d_alltheplaces,
    n3e_imports,
    n4_relevance,
    n5_resolve,
    n6_enrich,
    n7_verify,
    n8_score,
    n9_critic,
    n10_persist,
    n11_eval,
    n12_report,
)

logger = logging.getLogger(__name__)


# ── Fan-out router ────────────────────────────────────────────────────────────

def _route_sources(state: RunState) -> list[Send | str]:
    """
    After geo + keyword planning are both ready, fan out to enabled source nodes.
    At least one of N3a or N3b must be in the enabled set.
    """
    query_obj = state.get("query")
    if isinstance(query_obj, dict):
        query = QueryInput(**query_obj)
    elif isinstance(query_obj, QueryInput):
        query = query_obj
    else:
        query = QueryInput(keywords=["business"], location={})
    sources = getattr(query, "sources", {"overture", "osm"})

    sends: list[Send | str] = []

    if "overture" in sources:
        sends.append(Send("n3a_overture", state))
    if "osm" in sources:
        sends.append(Send("n3b_overpass", state))
    if "wikidata" in sources:
        sends.append(Send("n3c_wikidata", state))
    if "alltheplaces" in sources:
        sends.append(Send("n3d_alltheplaces", state))
    if "imports" in sources:
        sends.append(Send("n3e_imports", state))

    if not sends:
        # Safety: at least try OSM if nothing is enabled
        sends.append(Send("n3b_overpass", state))

    return sends


def _route_after_geo(state: RunState) -> str:
    """
    After GeoResolverAgent: if geo_confidence < 0.6, trigger disambiguation interrupt.
    Otherwise proceed to join point.
    """
    geo: GeoResolution | None = state.get("geo")
    if geo is None or geo.geo_confidence < 0.6:
        return "disambiguation_interrupt"
    return "join_geo_kw"


def _route_critic(state: RunState) -> str:
    """
    After QualityCritic: either loop back to enrichment (for borderline entities)
    or proceed to persist.
    """
    iteration = state.get("iteration", 0)
    if iteration >= 2:
        return "n10_persist"

    entities = state.get("entities", [])
    borderline = [
        e for e in entities
        if 0.45 <= getattr(e, "confidence", getattr(e, "relevance_p", 0.5)) <= 0.65
    ]
    budget_obj = state.get("budget")
    http_calls_used = budget_obj.http_calls_used if hasattr(budget_obj, "http_calls_used") else (budget_obj.get("http_calls_used", 0) if isinstance(budget_obj, dict) else 0)
    if borderline and http_calls_used < 400:
        return "n6_enrich"
    return "n10_persist"


def _join_geo_kw(s: RunState) -> RunState:
    return s


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_graph() -> Any:
    g: Any = StateGraph(RunState)

    # Nodes
    g.add_node("n0_input", n0_input.run)
    g.add_node("n1_geo", n1_geo.run)
    g.add_node("n2_keyword", n2_keyword.run)
    g.add_node("disambiguation_interrupt", n1_geo.disambiguation_interrupt)
    g.add_node("join_geo_kw", _join_geo_kw)   # pass-through join point
    g.add_node("n3a_overture", n3a_overture.run)
    g.add_node("n3b_overpass", n3b_overpass.run)
    g.add_node("n3c_wikidata", n3c_wikidata.run)
    g.add_node("n3d_alltheplaces", n3d_alltheplaces.run)
    g.add_node("n3e_imports", n3e_imports.run)
    g.add_node("n4_filter", n4_relevance.run)
    g.add_node("n5_resolve", n5_resolve.run)
    g.add_node("n6_enrich", n6_enrich.run)
    g.add_node("n7_verify", n7_verify.run)
    g.add_node("n8_score", n8_score.run)
    g.add_node("n9_critic", n9_critic.run)
    g.add_node("n10_persist", n10_persist.run)
    g.add_node("n11_eval", n11_eval.run)
    g.add_node("n12_report", n12_report.run)

    # Edges
    g.add_edge(START, "n0_input")

    # N0 fans out to N1 and N2 in parallel
    g.add_edge("n0_input", "n1_geo")
    g.add_edge("n0_input", "n2_keyword")

    # N1 → disambiguation or join
    g.add_conditional_edges("n1_geo", _route_after_geo, {
        "disambiguation_interrupt": "disambiguation_interrupt",
        "join_geo_kw": "join_geo_kw",
    })
    g.add_edge("disambiguation_interrupt", "n1_geo")  # retry after user picks

    # N2 → join
    g.add_edge("n2_keyword", "join_geo_kw")

    # Join → fan-out to sources
    g.add_conditional_edges("join_geo_kw", _route_sources)

    # All source nodes → N4 filter (fan-in via reducer)
    for src in ["n3a_overture", "n3b_overpass", "n3c_wikidata", "n3d_alltheplaces", "n3e_imports"]:
        g.add_edge(src, "n4_filter")

    # Linear pipeline after filter
    g.add_edge("n4_filter", "n5_resolve")
    g.add_edge("n5_resolve", "n6_enrich")
    g.add_edge("n6_enrich", "n7_verify")
    g.add_edge("n7_verify", "n8_score")
    g.add_edge("n8_score", "n9_critic")

    # Critic: loop or proceed
    g.add_conditional_edges("n9_critic", _route_critic, {
        "n6_enrich": "n6_enrich",
        "n10_persist": "n10_persist",
    })

    g.add_edge("n10_persist", "n11_eval")
    g.add_edge("n11_eval", "n12_report")
    g.add_edge("n12_report", END)

    return g


_COMPILED_GRAPHS: dict[int, Any] = {}


async def build_checkpointer(pool: Any | None = None) -> Any:
    """Build durable AsyncPostgresSaver or MemorySaver in testing."""
    if getattr(settings, "testing", False):
        return MemorySaver()
    if pool is None:
        pool = get_direct_async_pool()
    cp = AsyncPostgresSaver(cast(Any, pool))
    await cp.setup()
    assert hasattr(cp, "aput"), "checkpointer cannot be used with astream()"
    assert not isinstance(cp, MemorySaver), "refusing to boot with a non-durable checkpointer"
    return cp


def get_compiled_graph(checkpointer: Any | None = None) -> Any:
    """
    Return the compiled graph with checkpointer.
    Cached per running asyncio event loop so multi-loop test runners remain isolated.
    """
    try:
        loop = asyncio.get_running_loop()
        loop_id = id(loop)
    except RuntimeError:
        logger.warning("No running event loop found when resolving compiled graph; using fallback key")
        loop_id = 0

    if loop_id in _COMPILED_GRAPHS and checkpointer is None:
        return _COMPILED_GRAPHS[loop_id]

    if checkpointer is None:
        if getattr(settings, "testing", False):
            checkpointer = MemorySaver()
        else:
            pool = get_direct_async_pool()
            checkpointer = AsyncPostgresSaver(pool)  # type: ignore[arg-type]
            assert hasattr(checkpointer, "aput"), "checkpointer cannot be used with astream()"

    graph = build_graph()
    compiled = graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["disambiguation_interrupt"],
    )
    _COMPILED_GRAPHS[loop_id] = compiled
    return compiled


# ── Node list for doc/test consistency ───────────────────────────────────────

EXPECTED_NODES = [
    "n0_input", "n1_geo", "n2_keyword", "disambiguation_interrupt",
    "join_geo_kw",
    "n3a_overture", "n3b_overpass", "n3c_wikidata", "n3d_alltheplaces", "n3e_imports",
    "n4_filter", "n5_resolve", "n6_enrich", "n7_verify", "n8_score",
    "n9_critic", "n10_persist", "n11_eval", "n12_report",
]
