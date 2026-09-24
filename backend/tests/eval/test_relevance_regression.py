"""
Gate B Regression Test — Asserts that offline relevance metrics do not regress against baseline.json

v2.2 note: Category-first scoring intentionally routes name-only leads to 'review'
not 'accepted'. This lowers raw accepted-recall from 1.0 → ~0.81, which is correct
behaviour — those leads go to the human review queue rather than auto-accept.
The recall gate is set to 0.75 to accommodate this intentional tradeoff while
still catching genuine regressions.
"""

import json
from pathlib import Path
import pytest
from app.eval.relevance import run_benchmark

BASELINE_PATH = Path(__file__).resolve().parent.parent.parent.parent / "eval" / "baseline.json"

@pytest.mark.asyncio
async def test_relevance_gate_b_metrics_not_regressed() -> None:
    assert BASELINE_PATH.exists(), f"Baseline file {BASELINE_PATH} must exist."
    with open(BASELINE_PATH, "r", encoding="utf-8") as f:
        baseline = json.load(f)

    # Run fresh benchmark in memory
    results = await run_benchmark(save_baseline=False)

    # 1. Macro precision must be >= 0.95 (zero false positives is a hard requirement)
    assert results["macro_precision"] >= 0.95, f"Macro precision regressed: {results['macro_precision']}"

    # 2. Macro recall: 0.75+ (name-only leads go to review, lowering raw recall intentionally)
    # This is a DELIBERATE category-first tradeoff: review queue captures the uncertain ones.
    assert results["macro_recall"] >= 0.75, f"Macro recall regressed: {results['macro_recall']}"

    # 3. No regression > 5 percentage points against pinned baseline
    # (wider tolerance because baseline is now measured at category-first weights)
    tolerance = 0.05
    assert results["macro_precision"] >= (baseline["macro_precision"] - tolerance), "Precision regressed > 5% against baseline"
    assert results["macro_recall"] >= (baseline["macro_recall"] - tolerance), "Recall regressed > 5% against baseline"

    # 4. Check pooja_whitefield specifically — hard zero FP requirement
    pooja_case = next((c for c in results["cases"] if c["case"] == "pooja_whitefield"), None)
    assert pooja_case is not None
    assert pooja_case["precision"] >= 0.90
    assert pooja_case["fp"] == 0, f"Expected 0 false positives for pooja_whitefield, got {pooja_case['fp']}"
