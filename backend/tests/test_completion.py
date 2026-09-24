"""
tests/test_completion.py — Unit test suite for truth-telling completion reasons (§2.1).
"""

from __future__ import annotations

import pytest
from app.graph.completion import CompletionReason, decide_completion


def test_target_met():
    reason, details = decide_completion(accepted=30, target=30)
    assert reason == CompletionReason.TARGET_MET
    assert details == {}

    reason, details = decide_completion(accepted=35, target=30)
    assert reason == CompletionReason.TARGET_MET


def test_critical_error_and_cancelled():
    reason, _ = decide_completion(accepted=10, target=30, critical_error=True)
    assert reason == CompletionReason.FAILED

    reason, _ = decide_completion(accepted=10, target=30, cancelled=True)
    assert reason == CompletionReason.CANCELLED


def test_budget_exhausted():
    budget = {"exhausted": True, "which_limit": "wall_seconds"}
    reason, details = decide_completion(accepted=10, target=30, budget=budget)
    assert reason == CompletionReason.BUDGET_EXHAUSTED
    assert details.get("limit") == "wall_seconds"


def test_partial_sources():
    sources = {"any_failed": True, "failed_names": ["osm_overpass"]}
    reason, details = decide_completion(accepted=10, target=30, sources=sources)
    assert reason == CompletionReason.PARTIAL_SOURCES
    assert details.get("failed") == ["osm_overpass"]


def test_keyword_plan_matched_nothing():
    source_stats = {"overture": {"raw_count": 5439, "matched": 0}}
    reason, details = decide_completion(
        accepted=0, target=30, dedup={"candidates_seen": 0}, source_stats=source_stats, keyword="degree collage"
    )
    assert reason == CompletionReason.KEYWORD_PLAN_MATCHED_NOTHING
    assert details.get("raw_count") == 5439
    assert details.get("keyword") == "degree collage"


def test_no_candidates_found():
    source_stats = {"overture": {"raw_count": 0, "matched": 0}}
    reason, details = decide_completion(
        accepted=0, target=30, dedup={"candidates_seen": 0}, source_stats=source_stats, keyword="degree collage"
    )
    assert reason == CompletionReason.NO_CANDIDATES_FOUND
    assert details.get("raw_count") == 0


def test_no_new_leads_distinction():
    """Candidates were seen, but all matched existing database records — NOT exhaustion."""
    dedup = {
        "candidates_seen": 45,
        "new_businesses": 0,
        "matched_existing": 45,
        "prior_run_ids": ["run-1", "run-2"],
    }
    ladder = {
        "reached_final_rung": True,
        "last_rung_new_candidates": 0,
        "rungs": [{"rung": 0, "strategy": "base"}],
    }
    reason, details = decide_completion(
        accepted=0,
        target=30,
        ladder=ladder,
        dedup=dedup,
    )
    assert reason == CompletionReason.NO_NEW_LEADS
    assert details.get("already_known") == 45
    assert details.get("first_seen_runs") == ["run-1", "run-2"]


def test_low_relevance_precision_collapse():
    """Precision collapse: rejected far more than accepted (<5% accepted)."""
    dedup = {
        "candidates_seen": 200,
        "new_businesses": 5,
        "matched_existing": 0,
        "top_reject_codes": ["veto_brand", "low_evidence"],
    }
    reason, details = decide_completion(
        accepted=3,  # 3 / 200 = 1.5% < 5%
        target=30,
        dedup=dedup,
    )
    assert reason == CompletionReason.LOW_RELEVANCE
    assert details.get("candidates") == 200
    assert details.get("top_rejection_reasons") == ["veto_brand", "low_evidence"]


def test_region_exhausted_requires_all_four_proofs():
    """Region exhausted ONLY when all 4 conditions strictly hold."""
    ladder = {
        "reached_final_rung": True,
        "last_rung_new_candidates": 0,
        "rungs": [
            {"rung": 0, "strategy": "base"},
            {"rung": 1, "strategy": "host_categories"},
        ],
        "final_radius_m": 2000,
        "localities": ["HSR Layout"],
        "category_count": 47,
    }
    budget = {"exhausted": False}
    sources = {"any_failed": False, "failed_names": []}
    dedup = {"candidates_seen": 30, "new_businesses": 15, "matched_existing": 0}

    # All 4 proofs hold:
    reason, details = decide_completion(
        accepted=15,
        target=30,
        ladder=ladder,
        budget=budget,
        sources=sources,
        dedup=dedup,
    )
    assert reason == CompletionReason.REGION_EXHAUSTED
    assert details.get("rungs_tried") == ladder["rungs"]
    assert details.get("final_radius_m") == 2000
    assert details.get("categories_queried") == 47


def test_region_not_exhausted_if_ladder_incomplete():
    """If ladder didn't reach final rung, or last rung had candidates, it's not exhausted."""
    incomplete_ladder = {
        "reached_final_rung": False,
        "last_rung_new_candidates": 5,
    }
    reason, _ = decide_completion(
        accepted=15,
        target=30,
        ladder=incomplete_ladder,
    )
    assert reason != CompletionReason.REGION_EXHAUSTED
    assert reason == CompletionReason.LOW_RELEVANCE
