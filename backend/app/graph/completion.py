"""
app/graph/completion.py — Truth-telling completion reason decider.

Only declares region_exhausted when 4 concurrent proofs hold:
  1. Ladder reached final rung
  2. Last rung produced 0 new candidates
  3. Budget was not exhausted
  4. No sources failed

Otherwise outputs the true underlying cause:
  - keyword_plan_matched_nothing: sources returned places, but 0 matched the keyword plan
  - no_candidates_found: sources returned 0 raw places for the region
  - no_new_leads: candidates seen > 0 but all matched existing database records
  - low_relevance: precision collapse (accepted / candidates_seen < 5%)
  - budget_exhausted: hit wall clock or call budget
  - partial_sources: upstream connectors degraded or failed
  - target_met: target lead count satisfied
  - cancelled / failed: termination triggers
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class CompletionReason(StrEnum):
    TARGET_MET = "target_met"
    REGION_EXHAUSTED = "region_exhausted"
    KEYWORD_PLAN_MATCHED_NOTHING = "keyword_plan_matched_nothing"
    NO_CANDIDATES_FOUND = "no_candidates_found"
    NO_NEW_LEADS = "no_new_leads"
    BUDGET_EXHAUSTED = "budget_exhausted"
    PARTIAL_SOURCES = "partial_sources"
    LOW_RELEVANCE = "low_relevance"
    CANCELLED = "cancelled"
    FAILED = "failed"


def _get_val(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def decide_completion(
    *,
    accepted: int,
    target: int,
    ladder: Any = None,
    budget: Any = None,
    sources: Any = None,
    dedup: Any = None,
    source_stats: dict[str, Any] | None = None,
    keyword: str = "",
    cancelled: bool = False,
    critical_error: bool = False,
) -> tuple[CompletionReason, dict[str, Any]]:
    """
    Decide the exact honest completion reason based on observable evidence.
    Order matters: the most specific explanation wins.
    """
    if critical_error:
        return CompletionReason.FAILED, {}
    if cancelled:
        return CompletionReason.CANCELLED, {}
    if accepted >= target:
        return CompletionReason.TARGET_MET, {}

    # 1. Budget limits hit
    budget_exhausted = bool(_get_val(budget, "exhausted", False))
    which_limit = _get_val(budget, "which_limit", "wall_seconds")
    if budget_exhausted:
        return CompletionReason.BUDGET_EXHAUSTED, {"limit": which_limit}

    # 2. Source failures / degradation
    any_failed = bool(_get_val(sources, "any_failed", False))
    failed_names = _get_val(sources, "failed_names", []) or []
    if any_failed:
        return CompletionReason.PARTIAL_SOURCES, {"failed": failed_names}

    candidates_seen = int(_get_val(dedup, "candidates_seen", accepted) or accepted)

    # 3. Zero Candidates Ingestion: check raw counts vs matched
    if candidates_seen == 0 and accepted == 0:
        total_raw = 0
        if source_stats:
            for s_name, s_data in source_stats.items():
                if isinstance(s_data, dict):
                    total_raw += int(s_data.get("raw_count", 0) or 0)
        
        if total_raw > 0:
            return CompletionReason.KEYWORD_PLAN_MATCHED_NOTHING, {
                "raw_count": total_raw,
                "keyword": keyword,
                "matched": 0,
            }
        else:
            return CompletionReason.NO_CANDIDATES_FOUND, {
                "raw_count": 0,
                "keyword": keyword,
            }

    # 4. "You already have them" — NOT exhaustion
    new_businesses = int(_get_val(dedup, "new_businesses", 0) or 0)
    matched_existing = int(_get_val(dedup, "matched_existing", 0) or 0)
    prior_run_ids = _get_val(dedup, "prior_run_ids", []) or []

    if candidates_seen > 0 and new_businesses == 0 and matched_existing > 0:
        return CompletionReason.NO_NEW_LEADS, {
            "already_known": matched_existing,
            "first_seen_runs": prior_run_ids,
        }

    # 5. Precision collapse / low relevance (rejected far more than accepted)
    top_reject_codes = _get_val(dedup, "top_reject_codes", []) or []
    if candidates_seen > 0 and (accepted / max(candidates_seen, 1)) < 0.05:
        return CompletionReason.LOW_RELEVANCE, {
            "candidates": candidates_seen,
            "accepted": accepted,
            "top_rejection_reasons": top_reject_codes,
        }

    # 6. THE ONLY PATH TO "EXHAUSTED" — all four conditions required
    reached_final_rung = bool(_get_val(ladder, "reached_final_rung", False))
    last_rung_new_candidates = int(_get_val(ladder, "last_rung_new_candidates", 0) or 0)
    rungs = _get_val(ladder, "rungs", []) or []
    final_radius_m = _get_val(ladder, "final_radius_m", None)
    localities = _get_val(ladder, "localities", []) or []
    category_count = int(_get_val(ladder, "category_count", 1) or 1)

    if (
        reached_final_rung
        and last_rung_new_candidates == 0
        and not budget_exhausted
        and not any_failed
    ):
        return CompletionReason.REGION_EXHAUSTED, {
            "rungs_tried": rungs,
            "final_radius_m": final_radius_m,
            "localities_searched": localities,
            "categories_queried": category_count,
        }

    # Honest default when shortfall cannot be proven as exhausted
    return CompletionReason.LOW_RELEVANCE, {
        "note": "ladder incomplete — supply or precision shortfall undetermined",
        "candidates": candidates_seen,
        "accepted": accepted,
    }
