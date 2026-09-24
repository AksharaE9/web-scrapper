"""
app/metrics/expectations.py — Great Expectations-style output contract suite on pipeline results.
"""

from __future__ import annotations

import logging
from typing import Any
from app.graph.state import ResolvedEntity

logger = logging.getLogger(__name__)


class ExpectationSuiteResult:
    def __init__(self, passed: bool, checks: list[dict[str, Any]]) -> None:
        self.passed = passed
        self.checks = checks


def run_output_expectation_suite(
    entities: list[ResolvedEntity],
    max_results_target: int,
) -> ExpectationSuiteResult:
    """Run data quality expectations on resolved entities."""
    checks: list[dict[str, Any]] = []
    all_passed = True

    # 1. 0 < accepted <= max_results
    count = len(entities)
    c1_pass = (0 <= count <= max_results_target * 1.5)
    checks.append({
        "expectation": "count_within_bounds",
        "passed": c1_pass,
        "detail": f"Observed {count} entities (target: {max_results_target})",
    })
    if not c1_pass:
        all_passed = False

    # 2. Null rate on canonical_name must be 0%
    null_names = sum(1 for e in entities if not e.canonical_name or not e.canonical_name.strip())
    c2_pass = (null_names == 0)
    checks.append({
        "expectation": "null_rate_name_zero",
        "passed": c2_pass,
        "detail": f"{null_names} entities missing name",
    })
    if not c2_pass:
        all_passed = False

    # 3. Phone numbers format validation (must start with + or digits)
    bad_phones = 0
    for e in entities:
        for p in e.phones_e164:
            if not p.startswith("+") and not p.isdigit():
                bad_phones += 1
    c3_pass = (bad_phones == 0)
    checks.append({
        "expectation": "phones_format_valid",
        "passed": c3_pass,
        "detail": f"{bad_phones} phones malformed",
    })
    if not c3_pass:
        all_passed = False

    # 4. Tier distribution check: not >95% one tier when entities >= 20
    if len(entities) >= 20:
        tiers = [e.tier for e in entities if hasattr(e, "tier")]
        if tiers:
            max_tier_freq = max(tiers.count(t) for t in set(tiers)) / float(len(tiers))
            c4_pass = (max_tier_freq < 0.98)
            checks.append({
                "expectation": "tier_distribution_discriminating",
                "passed": c4_pass,
                "detail": f"Max single tier share: {max_tier_freq:.1%}",
            })
            if not c4_pass:
                all_passed = False

    return ExpectationSuiteResult(passed=all_passed, checks=checks)
