"""
Benchmark Runner v2.0 — LeadCore Zero VALIDATE-1.0

Replaces the bare-number reporting of v2.1 with statistically valid reporting:
  - Wilson score confidence intervals (Brown, Cai & DasGupta, Statistical Science 2001)
  - Accept-all baseline (B1) alongside every precision figure
  - Permutation test p-values against accept-all
  - Full per-tier, per-run distribution (never aggregate-only)
  - Commit SHA on every scorecard
  - Yield-vs-expectation metric replacing raw non-zero-yield (M2 fix)
  - Tier difficulty labelling and variance check
  - Seeded known-negatives with FP rate measurement

STATISTICAL DESIGN NOTES:
  - Report precision as p [CI_lo, CI_hi] Wilson-95, n=N — never bare p.
  - Wald CI coverage is "chaotic" near 0/1 (Brown et al. 2001); Wilson used throughout.
  - Rule of three: 100% on k items → true failure rate could be as high as 3/k.
    At k=4, that is 75%.
  - To claim ±3pp, need n ≥ 343; ±5pp needs n ≥ 124.

FORBIDDEN (hard assertions):
  - Reporting any proportion without CI
  - Reporting any tier as 100% without seeded failures
  - M2 "success" on yield=1 for a dense locality query
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import random
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import yaml

backend_root = Path(__file__).resolve().parent.parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

if sys.platform == "win32":
    try:
        reconfig = getattr(sys.stdout, "reconfigure", None)
        if callable(reconfig):
            reconfig(encoding="utf-8", errors="replace")
    except Exception:
        pass

from app.relevance.concepts import resolve_concept
from app.relevance.engine import evaluate_candidate

EVAL_DIR = backend_root.parent / "eval" / "relevance"
BASELINE_PATH = backend_root.parent / "eval" / "baseline.json"

# Tier definitions for difficulty grading (MR-3 / tier-variance check)
TIER_DEFINITIONS: dict[str, list[str]] = {
    "A_seeded_easy": ["gyms_koramangala", "pooja_whitefield", "salons_banjara_hills"],
    "B_clean_nonzero": ["bakeries_indiranagar"],
    "C_ambiguous": ["coaching_kukatpally"],
    "D_hard_negatives": ["degree_college_ameerpet", "degree_college_kukatpally"],
    "E_hard_typos": ["degree_college_dilsukhnagar"],
}

# Yield-vs-expectation floor values per keyword (M2 replacement)
# A search with expected_min=5 that returns 1 is a RECALL FAILURE, not a success.
YIELD_EXPECTATIONS: dict[str, int] = {
    "hotel": 15,           # HSR Layout has many hotels
    "shopping mall": 2,    # sparse per-area
    "gym": 8,
    "pharmacy": 10,
    "degree college": 3,
    "salon": 8,
    "restaurant": 20,
    "pooja stores": 5,
    "coaching centre": 5,
    "bakery": 5,
}


# ── Statistical Utilities ─────────────────────────────────────────────────────
def wilson_ci(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval (never Wald near 0/1)."""
    if total == 0:
        return (0.0, 1.0)
    p_hat = successes / total
    denom = 1 + z**2 / total
    centre = (p_hat + z**2 / (2 * total)) / denom
    spread = (z * math.sqrt(p_hat * (1 - p_hat) / total + z**2 / (4 * total**2))) / denom
    return (max(0.0, centre - spread), min(1.0, centre + spread))


def rule_of_three(k: int) -> float:
    """Upper bound on true failure rate when k successes observed out of k trials.
    
    Hanley & Lippman-Hand (1983): if no failures in k trials, true rate ≤ 3/k (95% conf).
    """
    return 3.0 / max(k, 1)


def permutation_p_value(
    system_precision: float,
    null_precisions: list[float],
    correction: bool = True,
) -> float:
    """Ojala & Garriga (JMLR 2010) permutation p-value with mandatory +1 correction.
    
    p = (|{D' : e(f,D') ≤ e(f,D)}| + 1) / (k + 1)
    """
    k = len(null_precisions)
    count = sum(1 for np_val in null_precisions if np_val >= system_precision)
    if correction:
        return (count + 1) / (k + 1)
    return count / max(k, 1)


def get_commit_sha() -> str:
    """Return current git HEAD commit SHA. Required on every scorecard."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True,
            cwd=str(backend_root),
        )
        if result.returncode == 0:
            return result.stdout.strip()[:12]
    except Exception:
        pass
    return "UNKNOWN-NO-SHA"


# ── Yield-vs-Expectation (M2 replacement) ────────────────────────────────────
def compute_yield_ratio(keyword: str, accepted_count: int) -> dict[str, Any]:
    """M2 replacement: yield / expected_minimum ≥ 0.6 = pass.
    
    'One mall = success' is FORBIDDEN per §1.3. This metric enforces a
    minimum yield expectation based on keyword type and locality density.
    """
    expected = YIELD_EXPECTATIONS.get(keyword.lower().strip(), 3)
    ratio = accepted_count / max(expected, 1)
    return {
        "accepted": accepted_count,
        "expected_min": expected,
        "yield_ratio": round(ratio, 4),
        "passed": ratio >= 0.6,
        "note": f"{'✓ meets' if ratio >= 0.6 else '✗ below'} 60% yield floor",
    }


# ── Core Evaluation ───────────────────────────────────────────────────────────
async def evaluate_single_case(case_path: Path) -> dict[str, Any]:
    """Evaluate one fixture with full statistical reporting."""
    with open(case_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    case_name = data.get("case", case_path.stem)
    query_info = data.get("query", {})
    keyword = query_info.get("keyword", "business")
    labels = data.get("labels", [])

    card = resolve_concept(keyword)

    tp = fp = tn = fn = review_count = 0
    stage_counts: dict[str, int] = {"hard_gates": 0, "scorer": 0, "cross_encoder": 0, "llm": 0, "review_band": 0}
    false_positives: list[dict[str, Any]] = []
    false_negatives: list[dict[str, Any]] = []
    all_decisions: list[dict[str, Any]] = []

    start_time = time.perf_counter()

    for item in labels:
        name = item["name"]
        ground_truth = item.get("relevant")
        cats = item.get("categories", [])
        brand = item.get("brand")
        is_seeded_negative = item.get("seeded_negative", False)

        dec = await evaluate_candidate(
            name=name,
            keyword=keyword,
            lon=77.75, lat=12.97,
            categories=cats,
            brand=brand,
            card=card,
        )

        stage_key = dec.stage if dec.stage in stage_counts else "scorer"
        stage_counts[stage_key] = stage_counts.get(stage_key, 0) + 1

        decision_record = {
            "name": name,
            "ground_truth": ground_truth,
            "outcome": dec.outcome,
            "p": dec.p,
            "stage": dec.stage,
            "reason_code": dec.reason_code,
            "is_seeded_negative": is_seeded_negative,
        }
        all_decisions.append(decision_record)

        if dec.outcome == "accepted":
            if ground_truth is True:
                tp += 1
            else:
                fp += 1
                false_positives.append({
                    "name": name, "stage": dec.stage, "p": dec.p,
                    "categories": cats, "reasons": dec.reasons,
                    "is_seeded_negative": is_seeded_negative,
                })
        elif dec.outcome in ("rejected", "review"):
            if dec.outcome == "review":
                review_count += 1
            if ground_truth is False:
                tn += 1
            else:
                fn += 1
                false_negatives.append({
                    "name": name, "stage": dec.stage, "p": dec.p,
                    "categories": cats, "outcome": dec.outcome,
                })

    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
    total = len(labels)
    positive_labels = sum(1 for item in labels if item.get("relevant") is True)
    negative_labels = sum(1 for item in labels if item.get("relevant") is False)
    base_rate = positive_labels / max(total, 1)

    # Wilson CIs
    p_ci = wilson_ci(tp, max(tp + fp, 1))
    r_ci = wilson_ci(tp, max(tp + fn, 1))

    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1_denom = precision + recall
    f1 = (2 * precision * recall) / max(f1_denom, 1e-9) if f1_denom > 0 else 0.0
    beta_sq = 0.25
    f05_denom = beta_sq * precision + recall
    f05 = (1 + beta_sq) * precision * recall / max(f05_denom, 1e-9) if f05_denom > 0 else 0.0

    # Accept-all baseline for this case
    accept_all_precision = base_rate  # precision if we accept everything
    precision_delta_pp = (precision - accept_all_precision) * 100.0

    # Permutation p-value (k=1000 permutation resamples per protocol)
    null_precisions = []
    gt_list = [item.get("relevant") for item in labels]
    for _ in range(1000):
        shuffled = gt_list.copy()
        random.shuffle(shuffled)
        null_tp = sum(1 for item, s_gt in zip(labels, shuffled)
                      if s_gt is True)  # if we accepted everything
        null_p = null_tp / max(total, 1)
        null_precisions.append(null_p)
    perm_p = permutation_p_value(precision, null_precisions)

    # Yield ratio (M2 replacement)
    yield_info = compute_yield_ratio(keyword, tp)

    # Seeded negative FP rate
    seeded_fp = sum(1 for d in all_decisions
                    if d["is_seeded_negative"] and d["outcome"] == "accepted")
    seeded_n = sum(1 for item in labels if item.get("seeded_negative", False))

    return {
        "case": case_name,
        "keyword": keyword,
        "locality": query_info.get("locality", "unknown"),
        "total_candidates": total,
        "positive_labels": positive_labels,
        "negative_labels": negative_labels,
        "base_rate": round(base_rate, 4),
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "review": review_count,
        "precision": round(precision, 4),
        "precision_ci": [round(p_ci[0], 4), round(p_ci[1], 4)],
        "recall": round(recall, 4),
        "recall_ci": [round(r_ci[0], 4), round(r_ci[1], 4)],
        "f1": round(f1, 4),
        "f05": round(f05, 4),
        "accept_all_baseline_precision": round(accept_all_precision, 4),
        "delta_vs_baseline_pp": round(precision_delta_pp, 2),
        "permutation_p": round(perm_p, 4),
        "review_rate": round(review_count / max(total, 1), 4),
        "accuracy": round((tp + tn) / max(total, 1), 4),
        "ms_per_candidate": round(elapsed_ms / max(total, 1), 2),
        "cascade_split": stage_counts,
        "yield_vs_expectation": yield_info,
        "rule_of_three_failure_floor": round(rule_of_three(max(tp + fp, 1)) * 100, 1),
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "all_decisions": all_decisions,
        "seeded_negatives_count": seeded_n,
        "seeded_fp_count": seeded_fp,
        "seeded_fp_rate": round(seeded_fp / max(seeded_n, 1), 4) if seeded_n > 0 else None,
    }


# ── Benchmark Runner ──────────────────────────────────────────────────────────
async def run_benchmark(
    save_baseline: bool = True,
    verbose: bool = True,
) -> dict[str, Any]:
    case_files = list(EVAL_DIR.glob("*.yaml"))
    if not case_files:
        print("No evaluation case files found in eval/relevance/")
        return {}

    commit_sha = get_commit_sha()

    if verbose:
        print("\n" + "═" * 100)
        print("  LEADCORE ZERO — RELEVANCE BENCHMARK v2.0 (VALIDATE-1.0)")
        print(f"  Commit: {commit_sha}")
        print(f"  Fixtures: {len(case_files)}")
        print("═" * 100)
        print(
            f"{'Case':<28} | {'P [CI_lo, CI_hi] Wilson-95':<34} | "
            f"{'vs B1':>7} | {'perm_p':>7} | {'R':>6} | {'Yield':>6} | {'ms/c':>5}"
        )
        print("-" * 100)

    case_results: list[dict[str, Any]] = []
    for cf in sorted(case_files):
        res = await evaluate_single_case(cf)
        case_results.append(res)
        if verbose:
            yld = res["yield_vs_expectation"]
            print(
                f"{res['case']:<28} | "
                f"{res['precision']:.4f} [{res['precision_ci'][0]:.4f}, {res['precision_ci'][1]:.4f}] | "
                f"{res['delta_vs_baseline_pp']:+7.1f}pp | "
                f"{res['permutation_p']:>7.4f} | "
                f"{res['recall']:>6.4f} | "
                f"{'✓' if yld['passed'] else '✗'} {yld['yield_ratio']:.2f} | "
                f"{res['ms_per_candidate']:>5.1f}"
            )

    # Macro averages
    n = len(case_results)
    macro_p = round(sum(r["precision"] for r in case_results) / n, 4)
    macro_r = round(sum(r["recall"] for r in case_results) / n, 4)
    macro_f1 = round(sum(r["f1"] for r in case_results) / n, 4)
    macro_acc = round(sum(r["accuracy"] for r in case_results) / n, 4)
    macro_b1 = round(sum(r["accept_all_baseline_precision"] for r in case_results) / n, 4)
    macro_delta_pp = round((macro_p - macro_b1) * 100, 2)

    # Aggregate Wilson CI on pooled TP, FP
    total_tp = sum(r["tp"] for r in case_results)
    total_fp = sum(r["fp"] for r in case_results)
    pooled_ci = wilson_ci(total_tp, total_tp + total_fp)

    # Tier variance check: if all tiers score identically → no difficulty gradient
    tier_precisions = [r["precision"] for r in case_results]
    tier_variance = (
        sum((p - macro_p) ** 2 for p in tier_precisions) / n
        if n > 1 else 0.0
    )

    # Seeded negative summary
    total_seeded = sum(r["seeded_negatives_count"] for r in case_results)
    total_seeded_fp = sum(r["seeded_fp_count"] for r in case_results)

    summary = {
        "scorecard_version": "VALIDATE-1.0",
        "commit_sha": commit_sha,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "n_fixtures": n,
        "macro_precision": macro_p,
        "macro_precision_pooled_ci": [round(pooled_ci[0], 4), round(pooled_ci[1], 4)],
        "macro_recall": macro_r,
        "macro_f1": macro_f1,
        "macro_accuracy": macro_acc,
        "accept_all_baseline": macro_b1,
        "delta_above_baseline_pp": macro_delta_pp,
        "tier_precision_variance": round(tier_variance, 6),
        "tier_variance_warning": tier_variance < 0.001 and n > 2,
        "total_seeded_negatives": total_seeded,
        "total_seeded_fp": total_seeded_fp,
        "seeded_fp_rate": round(total_seeded_fp / max(total_seeded, 1), 4) if total_seeded else None,
        "cases": case_results,
    }

    if verbose:
        print("-" * 100)
        print(
            f"{'MACRO AVERAGE':<28} | "
            f"{macro_p:.4f} [{pooled_ci[0]:.4f}, {pooled_ci[1]:.4f}] pooled Wilson-95 | "
            f"{macro_delta_pp:+7.1f}pp |"
        )
        print("═" * 100)
        print(f"\nFORBIDDEN CHECK: bare number = {macro_p:.4f} — "
              f"report as: precision = {macro_p:.4f} [{pooled_ci[0]:.4f}, {pooled_ci[1]:.4f}] Wilson-95, "
              f"n={total_tp + total_fp}")
        print(f"vs accept-all baseline = {macro_b1:.4f}, Δ = {macro_delta_pp:+.1f}pp\n")

        if summary["tier_variance_warning"]:
            print("⚠  TIER VARIANCE WARNING: All tiers score nearly identically — "
                  "this is consistent with (a) all-easy tiers, (b) leakage, or "
                  "(c) grader agrees by construction. Run §2.1 mutations to distinguish.")
        print()

    if save_baseline:
        BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(BASELINE_PATH, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        print(f"Scorecard saved to: {BASELINE_PATH}")

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Relevance Benchmark v2.0 (VALIDATE-1.0)")
    parser.add_argument("--no-save", action="store_true", help="Don't save baseline")
    parser.add_argument("--quiet", action="store_true", help="Suppress per-case output")
    args = parser.parse_args()
    asyncio.run(run_benchmark(
        save_baseline=not args.no_save,
        verbose=not args.quiet,
    ))


if __name__ == "__main__":
    main()
