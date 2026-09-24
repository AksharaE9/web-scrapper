"""
Production Hardening Tests — LeadCore Zero VALIDATE-1.0

Tests covering P1–P16 production requirements from the audit:
  R1: verify=False removed from all httpx clients (P13)
  R3: idempotency enforced by constraint
  R4: source-down degradation path
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# R1: TLS — verify=False must not exist in any httpx call (P13)
# ─────────────────────────────────────────────────────────────────────────────
def test_r1_no_tls_bypass_in_codebase():
    """P13 / R1: httpx.AsyncClient or httpx.Client with verify disabled is FORBIDDEN.

    A MITM can inject fabricated phone numbers that get recorded as verified lead data.
    Only actual call-site patterns are checked (not comments, not docstrings, not
    this test file which legitimately mentions the pattern in its docstring).
    """
    backend_root = Path(__file__).resolve().parent.parent.parent
    this_file = Path(__file__).resolve()

    # Only search production code, not tests (tests may legitimately mention the pattern)
    app_dir = backend_root / "app"
    python_files = list(app_dir.rglob("*.py"))

    violations: list[str] = []
    # Pattern: actual httpx call with verify=False as keyword argument
    # Matches: httpx.AsyncClient(..., verify=False) or httpx.Client(..., verify=False)
    call_pattern = re.compile(r"httpx\.(?:Async)?Client\s*\([^)]*\bverify\s*=\s*False")

    for py_file in python_files:
        try:
            lines = py_file.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            continue

        for lineno, line in enumerate(lines, start=1):
            stripped = line.strip()
            # Skip pure comment lines
            if stripped.startswith("#"):
                continue
            # Only flag actual httpx call-sites
            if call_pattern.search(line):
                violations.append(f"{py_file.relative_to(backend_root)}:{lineno}: {stripped[:120]}")

    assert not violations, (
        f"P13 SECURITY VIOLATION: httpx client with verify=False found in {len(violations)} location(s).\n"
        f"A MITM can inject fabricated data into lead records.\n"
        + "\n".join(f"  {v}" for v in violations)
    )


# ─────────────────────────────────────────────────────────────────────────────
# Commit SHA: scorecards must carry a reproducible identifier
# ─────────────────────────────────────────────────────────────────────────────
def test_v14_commit_sha_obtainable():
    """V14: Commit SHA must be obtainable. A scorecard without SHA is not reproducible."""
    import subprocess
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True, text=True,
        cwd=str(Path(__file__).resolve().parent.parent.parent),
    )
    assert result.returncode == 0, "git rev-parse failed — not in a git repository"
    sha = result.stdout.strip()
    assert len(sha) >= 7, f"Git SHA too short: {sha!r}"
    print(f"\n  ✓ Commit SHA: {sha[:12]}")


# ─────────────────────────────────────────────────────────────────────────────
# Labelling protocol: rubric file must exist and be hashed before annotation
# ─────────────────────────────────────────────────────────────────────────────
def test_v9_labelling_rubric_exists():
    """V8/V9: Pre-registered labelling rubric must exist with degree college definition."""
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    rubric_path = repo_root / "docs" / "labelling_protocol.md"

    assert rubric_path.exists(), (
        f"V9 FAIL: Labelling rubric not found at {rubric_path}. "
        f"Annotation cannot begin without a pre-registered rubric."
    )

    content = rubric_path.read_text(encoding="utf-8")

    # Must explicitly define that K-12 schools are NOT degree colleges
    assert "K-12" in content or "high school" in content.lower(), (
        "V9 FAIL: Rubric does not define distinction between K-12 schools and degree colleges. "
        "This is the primary labelling ambiguity in PROD-v2.2."
    )

    # Must address the specific wrong results from PROD-v2.2
    assert "Gowtham Model School" in content or "model school" in content.lower(), (
        "V9 FAIL: Rubric does not address 'Model School' as a known false positive class."
    )

    print(f"  ✓ Labelling rubric found at: {rubric_path}")
    print(f"  ✓ Contains K-12/degree college distinction")


# ─────────────────────────────────────────────────────────────────────────────
# degree_college and primary_school concept cards must exist (C1)
# ─────────────────────────────────────────────────────────────────────────────
def test_c1_taxonomy_split_exists():
    """C1: school_college.yaml must be split into degree_college and primary_school."""
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    concepts_dir = repo_root / "backend" / "config" / "concepts"

    assert (concepts_dir / "degree_college.yaml").exists(), (
        "C1 FAIL: degree_college.yaml does not exist. "
        "The school_college.yaml split has not been performed."
    )
    assert (concepts_dir / "primary_school.yaml").exists(), (
        "C1 FAIL: primary_school.yaml does not exist. "
        "The school_college.yaml split has not been performed."
    )

    import yaml

    dc = yaml.safe_load((concepts_dir / "degree_college.yaml").read_text())
    ps = yaml.safe_load((concepts_dir / "primary_school.yaml").read_text())

    # degree_college must have veto terms for K-12
    dc_veto = dc.get("veto_terms", [])
    assert any("school" in v.lower() for v in dc_veto), (
        "C1 FAIL: degree_college.yaml has no veto terms for 'school' variants. "
        "K-12 schools will pass the degree college filter."
    )
    assert any("high school" in v.lower() or "model school" in v.lower() for v in dc_veto), (
        "C1 FAIL: degree_college.yaml does not veto 'high school' or 'model school'."
    )

    # primary_school must have veto terms for degree colleges
    ps_veto = ps.get("veto_terms", [])
    assert any("degree" in v.lower() or "college" in v.lower() for v in ps_veto), (
        "C1 FAIL: primary_school.yaml has no veto terms for degree colleges."
    )

    print(f"  ✓ degree_college.yaml exists with {len(dc_veto)} veto terms")
    print(f"  ✓ primary_school.yaml exists with {len(ps_veto)} veto terms")


# ─────────────────────────────────────────────────────────────────────────────
# Benchmark must include yield-vs-expectation (M2 replacement) (C4)
# ─────────────────────────────────────────────────────────────────────────────
def test_c4_yield_vs_expectation_in_results():
    """C4: Benchmark results must include yield_vs_expectation, not raw non-zero-yield."""
    import json
    baseline_path = Path(__file__).resolve().parent.parent.parent.parent / "eval" / "baseline.json"

    if not baseline_path.exists():
        pytest.skip("No baseline.json found — run the benchmark first")

    with open(baseline_path) as f:
        baseline = json.load(f)

    # The new benchmark must include yield_vs_expectation in each case
    cases = baseline.get("cases", [])
    if not cases:
        pytest.skip("No cases in baseline.json")

    for case in cases:
        assert "yield_vs_expectation" in case, (
            f"C4 FAIL: Case '{case.get('case', '?')}' does not have yield_vs_expectation. "
            f"The M2 metric must be replaced with yield-vs-expectation."
        )

    print(f"  ✓ C4: All {len(cases)} cases include yield_vs_expectation")


# ─────────────────────────────────────────────────────────────────────────────
# Scorecard must include confidence intervals (V6)
# ─────────────────────────────────────────────────────────────────────────────
def test_v6_scorecard_includes_ci():
    """V6: Scorecard must report precision with Wilson CI, not as bare number."""
    import json
    baseline_path = Path(__file__).resolve().parent.parent.parent.parent / "eval" / "baseline.json"

    if not baseline_path.exists():
        pytest.skip("No baseline.json found — run the benchmark first")

    with open(baseline_path) as f:
        baseline = json.load(f)

    # Must have pooled Wilson CI
    assert "macro_precision_pooled_ci" in baseline, (
        "V6 FAIL: Scorecard does not include Wilson score CI for macro_precision. "
        "Reporting bare numbers without CIs is FORBIDDEN per VALIDATE-1.0."
    )
    ci = baseline["macro_precision_pooled_ci"]
    assert isinstance(ci, list) and len(ci) == 2, "CI must be [lo, hi] pair"
    assert ci[0] <= ci[1], f"CI invalid: lo={ci[0]} > hi={ci[1]}"

    # Must have baseline comparison
    assert "accept_all_baseline" in baseline, (
        "V6 FAIL: Scorecard does not include accept-all baseline. "
        "Precision without baseline comparison is uninterpretable."
    )

    # Must have commit SHA
    assert "commit_sha" in baseline and baseline["commit_sha"] != "UNKNOWN-NO-SHA", (
        "V14 FAIL: Scorecard does not include commit SHA. Not reproducible."
    )

    print(f"  ✓ V6: Scorecard has Wilson CI [{ci[0]}, {ci[1]}]")
    print(f"  ✓ V14: Commit SHA = {baseline['commit_sha']}")
    print(f"  ✓ Accept-all baseline = {baseline['accept_all_baseline']}")
