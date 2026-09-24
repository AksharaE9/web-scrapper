"""
tests/unit/test_outcome_table.py — Outcome Classifier Decision Table Tests
"""

from __future__ import annotations

import pytest
from app.graph.completion import CompletionReason, decide_completion


def test_outcome_target_met():
    reason, details = decide_completion(accepted=50, target=50)
    assert reason == CompletionReason.TARGET_MET


def test_outcome_target_exceeded():
    reason, details = decide_completion(accepted=65, target=50)
    assert reason == CompletionReason.TARGET_MET


def test_outcome_budget_exhausted():
    budget = {"exhausted": True, "which_limit": "wall_seconds"}
    reason, details = decide_completion(accepted=33, target=50, budget=budget)
    assert reason == CompletionReason.BUDGET_EXHAUSTED
    assert details.get("limit") == "wall_seconds"


def test_outcome_partial_sources():
    sources = {"any_failed": True, "failed_names": ["osm_overpass"]}
    reason, details = decide_completion(accepted=33, target=50, sources=sources)
    assert reason == CompletionReason.PARTIAL_SOURCES
    assert "osm_overpass" in details.get("failed", [])


def test_outcome_no_new_leads():
    dedup = {
        "candidates_seen": 50,
        "new_businesses": 0,
        "matched_existing": 50,
        "prior_run_ids": ["run_prev"],
    }
    reason, details = decide_completion(
        accepted=0,
        target=50,
        dedup=dedup,
    )
    assert reason == CompletionReason.NO_NEW_LEADS
    assert details.get("already_known") == 50


def test_outcome_low_relevance_shortfall():
    """When accepted < target and region was not exhausted (precision shortfall)."""
    reason, details = decide_completion(
        accepted=33,
        target=50,
        ladder={"reached_final_rung": False},
        dedup={"candidates_seen": 83},
    )
    assert reason == CompletionReason.LOW_RELEVANCE
