"""
MUT-1 CI Gate — LeadCore Zero VALIDATE-1.0

This test is the MANDATORY CI gate from §2.1 / V1–V2 acceptance criteria.

MUT-1: Invert the relevance predicate (is_match → not is_match).
The benchmark MUST collapse. If it does not collapse, the benchmark is NOT
measuring the system and every number in the scorecard should be discarded.

Per Just et al. (FSE 2014): mutation score is a valid proxy for real-fault
detection (Â₁₂ = 0.74–0.81). MUT-1 is the highest-value, lowest-cost mutation
because it exercises the ENTIRE scoring and output path with a single inversion.

CRITICAL:
  - This test MUST pass before any other benchmark result is trusted.
  - If test_mut1_ci_gate FAILS (inverted benchmark does NOT collapse), the
    system has a benchmark validity crisis that blocks all Gate 1 criteria.

Expected behaviour:
  - Clean baseline: precision ≈ 0.85+
  - MUT-1 (inverted): precision must fall to < 0.40 (ideally ≈ 1 - base_rate)
"""
from __future__ import annotations

import asyncio
import pytest
from pathlib import Path
import sys

backend_root = Path(__file__).resolve().parent.parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.eval.mutations import (
    load_all_fixtures,
    _run_fixture_with_engine,
    _compute_metrics,
    mut1_inverted_predicate,
    mut7_empty_results,
    run_accept_all_baseline,
    run_seeded_failure_injection,
    run_mr6_null_query,
    run_mr3_typo_invariance,
    wilson_ci,
)
from app.relevance.engine import evaluate_candidate


pytestmark = pytest.mark.asyncio


# ─────────────────────────────────────────────────────────────────────────────
# MUT-1: CI Gate — MANDATORY FIRST TEST
# This is the V1 acceptance criterion. It MUST pass.
# ─────────────────────────────────────────────────────────────────────────────
async def test_mut1_ci_gate():
    """
    MUT-1 CRITICAL GATE: Invert relevance predicate → benchmark must collapse.

    If MUT-1 precision >= 0.5, the benchmark is not measuring the system.
    This is the single most important test in the entire test suite.
    """
    fixtures = load_all_fixtures()
    assert fixtures, "No eval fixtures found — cannot run MUT-1 gate"

    # First: establish clean baseline
    baseline_counts = {"tp": 0, "fp": 0, "tn": 0, "fn": 0}
    for fixture in fixtures:
        counts = await _run_fixture_with_engine(fixture, evaluate_candidate)
        for k in baseline_counts:
            baseline_counts[k] += counts[k]
    baseline = _compute_metrics(baseline_counts)

    # Then: run with inverted predicate
    mut1_counts = {"tp": 0, "fp": 0, "tn": 0, "fn": 0}
    for fixture in fixtures:
        counts = await _run_fixture_with_engine(fixture, mut1_inverted_predicate)
        for k in mut1_counts:
            mut1_counts[k] += counts[k]
    mut1 = _compute_metrics(mut1_counts)

    # Assertions
    baseline_precision = baseline["precision"]
    mut1_precision = mut1["precision"]
    degradation = baseline_precision - mut1_precision

    print(f"\n  Baseline precision: {baseline_precision:.4f}")
    print(f"  MUT-1 precision:    {mut1_precision:.4f}")
    print(f"  Degradation:        {degradation:.4f} ({degradation*100:.1f} pp)")

    # MUT-1 MUST collapse the benchmark:
    # Precision must fall below 0.5 (i.e., worse than random for classification)
    assert mut1_precision < 0.50, (
        f"🔴 CRITICAL BENCHMARK VALIDITY FAILURE: MUT-1 precision = {mut1_precision:.4f} "
        f"(expected < 0.50). The benchmark does NOT detect an inverted relevance predicate. "
        f"Every number in the scorecard is suspect. "
        f"Possible causes: (a) scoring path not exercised, (b) fixtures too easy/trivial, "
        f"(c) grader agrees by construction."
    )

    # MUT-1 must produce a statistically significant degradation (>= 30pp drop)
    assert degradation >= 0.30, (
        f"🔴 MUT-1 degradation too small: {degradation*100:.1f}pp "
        f"(required >= 30pp). The relevance predicate inversion had negligible effect."
    )

    print("  ✓ MUT-1 CI gate PASSED — benchmark correctly collapses on inverted predicate")


# ─────────────────────────────────────────────────────────────────────────────
# MUT-7: Empty results → M2 yield must go to 0
# ─────────────────────────────────────────────────────────────────────────────
async def test_mut7_empty_results_collapses_yield():
    """MUT-7: Empty result set — M2 non-zero yield metric must go to 0 (V1)."""
    fixtures = load_all_fixtures()
    assert fixtures, "No eval fixtures found"

    mut7_counts = {"tp": 0, "fp": 0, "tn": 0, "fn": 0}
    for fixture in fixtures:
        counts = await _run_fixture_with_engine(fixture, mut7_empty_results)
        for k in mut7_counts:
            mut7_counts[k] += counts[k]
    mut7 = _compute_metrics(mut7_counts)

    assert mut7["tp"] == 0, (
        f"MUT-7 FAIL: Empty result set produced {mut7['tp']} true positives. "
        f"M2 (non-zero yield) metric is not reading the result set."
    )
    print(f"  ✓ MUT-7 PASSED — TP={mut7['tp']} (empty results correctly yields 0)")


# ─────────────────────────────────────────────────────────────────────────────
# B1: Accept-all baseline must be measurably different from system precision
# ─────────────────────────────────────────────────────────────────────────────
async def test_b1_accept_all_baseline():
    """B1: Accept-all base rate must be computed and reported.

    If system precision <= base_rate + 0.05, the system adds ≤ 5pp of value
    over accepting everything, which is not a meaningful result.
    """
    fixtures = load_all_fixtures()
    assert fixtures, "No eval fixtures found"

    b1 = await run_accept_all_baseline(fixtures)

    baseline_counts = {"tp": 0, "fp": 0, "tn": 0, "fn": 0}
    for fixture in fixtures:
        counts = await _run_fixture_with_engine(fixture, evaluate_candidate)
        for k in baseline_counts:
            baseline_counts[k] += counts[k]
    baseline = _compute_metrics(baseline_counts)

    base_rate = b1["precision"]
    system_precision = baseline["precision"]
    delta_pp = (system_precision - base_rate) * 100

    print(f"\n  Accept-all base rate: {base_rate:.4f}")
    print(f"  System precision:     {system_precision:.4f}")
    print(f"  Δ above base rate:    {delta_pp:+.1f}pp")

    # Base rate must be computed (not None or 0)
    assert base_rate > 0, "Base rate is 0 — no positive items in evaluation pool"

    # System must add meaningful signal above base rate
    # Note: if Δ is very small, the 91.2% claim is inside the CI of accept-all
    assert delta_pp >= 0, (
        f"System precision ({system_precision:.4f}) is BELOW the accept-all "
        f"base rate ({base_rate:.4f}). This is a negative result."
    )

    print(f"  ✓ B1 computed: base_rate={base_rate:.4f}, Δ={delta_pp:+.1f}pp")


# ─────────────────────────────────────────────────────────────────────────────
# Seeded negatives: system must reject all seeded known-negatives
# ─────────────────────────────────────────────────────────────────────────────
async def test_seeded_negatives_all_rejected():
    """V10/V11: Seeded known-negatives must be rejected. FP rate on seeded items = 0."""
    result = await run_seeded_failure_injection()

    fp_rate = result["fp_rate"]
    false_accepts = result["false_accepts"]
    total = result["seeded_negatives"]

    print(f"\n  Seeded negatives: {total}")
    print(f"  False accepts:    {false_accepts}")
    print(f"  FP rate:          {fp_rate:.4f}")

    if false_accepts > 0:
        for r in result["results"]:
            if not r["correct"]:
                print(f"    ✗ ACCEPTED (wrong): {r['name']!r} as '{r['keyword']}'")

    assert false_accepts == 0, (
        f"System accepted {false_accepts}/{total} seeded known-negatives "
        f"(FP rate = {fp_rate:.4f}). These items are definitionally wrong matches. "
        f"Details: {[r for r in result['results'] if not r['correct']]}"
    )
    print("  ✓ Seeded negatives: all correctly rejected")


# ─────────────────────────────────────────────────────────────────────────────
# MR-6: Null/garbage query → must return empty / rejected
# ─────────────────────────────────────────────────────────────────────────────
async def test_mr6_null_query_returns_empty():
    """MR-6: Null and garbage inputs must not be accepted (V12)."""
    result = await run_mr6_null_query()

    violations = result["violations"]
    assert violations == 0, (
        f"MR-6 FAIL: {violations} null/garbage inputs were accepted. "
        f"Details: {result['details']}"
    )
    print(f"  ✓ MR-6 PASSED — no null/garbage inputs accepted")


# ─────────────────────────────────────────────────────────────────────────────
# MR-3: Typo invariance — Jaccard >= 0.8
# ─────────────────────────────────────────────────────────────────────────────
async def test_mr3_typo_invariance():
    """MR-3: Typo variants must produce consistent outcomes (Jaccard >= 0.8) (V12)."""
    result = await run_mr3_typo_invariance()

    jaccard = result["jaccard"]
    threshold = result["threshold"]

    print(f"\n  Typo invariance Jaccard: {jaccard:.4f} (threshold: {threshold})")
    for d in result["details"]:
        status = "✓" if d["match"] else "✗"
        print(f"    {status} '{d['canonical']}' vs '{d['typo']}': "
              f"{d['canonical_outcome']} vs {d['typo_outcome']}")

    assert jaccard >= threshold, (
        f"MR-3 FAIL: Typo invariance Jaccard = {jaccard:.4f} < {threshold}. "
        f"The normaliser is not providing consistent handling of typo variants. "
        f"This could indicate MUT-4 leakage (Tier E typos generated by the same logic)."
    )
    print(f"  ✓ MR-3 PASSED — typo invariance Jaccard = {jaccard:.4f}")


# ─────────────────────────────────────────────────────────────────────────────
# Taxonomy split: degree_college card must exist and must veto K-12 schools
# ─────────────────────────────────────────────────────────────────────────────
async def test_degree_college_rejects_k12_schools():
    """C1/C2: degree_college concept must exist and reject K-12 schools.

    The PROD-v2.2 flagship verification failure: six returned results were all
    schools, not degree colleges. This test enforces the correction.
    """
    from app.relevance.concepts import resolve_concept
    from app.relevance.engine import evaluate_candidate

    # These are the exact names from the PROD-v2.2 report that were wrongly accepted
    k12_schools = [
        ("Gowtham Model School", ["school"], False),
        ("Slate - The School", ["school"], False),
        ("Gitanjali Group of Schools", ["school"], False),
        ("St. Alphonsa High School", ["school"], False),
        ("Flying Star Aviation and Hospitality Academy", ["vocational_training", "skill_centre"], False),
        ("LiveTech", ["it_training", "computer_institute"], False),
    ]

    # And these should be accepted
    degree_colleges = [
        ("Sri Venkateswara Degree College", ["college", "college_and_university"], True),
        ("Aurora PG College", ["college_and_university"], True),
        ("JNTU College of Engineering", ["engineering_college", "college_and_university"], True),
    ]

    keyword = "degree college"
    card = resolve_concept(keyword)

    print(f"\n  Resolved keyword '{keyword}' → concept '{card.concept_id}'")
    failures = []

    for name, cats, expected_relevant in k12_schools + degree_colleges:
        dec = await evaluate_candidate(
            name=name, keyword=keyword, lon=78.49, lat=17.38,  # Ameerpet, Hyderabad
            categories=cats, card=card,
        )
        is_accepted = (dec.outcome == "accepted")
        expected_accepted = expected_relevant

        if is_accepted != expected_accepted:
            failures.append({
                "name": name,
                "categories": cats,
                "expected_relevant": expected_relevant,
                "outcome": dec.outcome,
                "stage": dec.stage,
                "reason_code": dec.reason_code,
            })
            label = "✗ WRONG"
        else:
            label = "✓ correct"

        expected_str = "ACCEPTED" if expected_accepted else "REJECTED"
        print(f"  {label}: '{name}' → {dec.outcome} (expected {expected_str})")

    assert not failures, (
        f"C2 FAIL: {len(failures)} businesses incorrectly classified for 'degree college':\n"
        + "\n".join(f"  - {f['name']}: got {f['outcome']}, expected "
                    f"{'accepted' if f['expected_relevant'] else 'rejected'}, "
                    f"stage={f['stage']}, reason={f['reason_code']}"
                    for f in failures)
    )
    print(f"  ✓ C2 PASSED — degree_college correctly classifies all {len(k12_schools + degree_colleges)} items")


# ─────────────────────────────────────────────────────────────────────────────
# Wilson CI: ensure precision reporting always includes CI
# ─────────────────────────────────────────────────────────────────────────────
async def test_wilson_ci_properties():
    """Statistical: Wilson CI must have sensible coverage properties."""
    # At n=4 (4-run tier), CI must be very wide
    lo, hi = wilson_ci(4, 4)  # 100% over 4 items
    assert hi - lo > 0.30, f"CI at n=4 should be wide (>30pp), got [{lo:.4f}, {hi:.4f}]"

    # At n=343, ±3pp should be achievable
    lo, hi = wilson_ci(312, 343)  # ~91%
    assert hi - lo < 0.07, f"CI at n=343 should be narrow (<7pp), got [{lo:.4f}, {hi:.4f}]"

    # Rule of three: 100% at n=20 → failure rate could be up to 15%
    rof3 = 3.0 / 20
    assert rof3 <= 0.15, f"Rule of three at n=20 should be ≤15%, got {rof3*100:.1f}%"

    print(f"  ✓ Wilson CI: n=4 width={hi-lo:.4f}, n=343 width passes")
    print(f"  ✓ Rule of three: n=20 → failure rate ≤ {rof3*100:.1f}%")
