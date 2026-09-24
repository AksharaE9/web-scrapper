"""
R4 — Evidence Scorer (Calibrated Logistic + Structural Defining-Signal Rule) v2.2

Evaluates feature vector f through calibrated logistic model p = σ(w·f + b).
Enforces structural defining-signal constraint: a lead cannot be accepted
without at least one PRIMARY defining signal (f_def_cat + f_def_osm + f_def_web >= 1).
f_def_name alone is NOT a primary signal in v2.2 — see f_name_only_primary.

Weight schema (v2.2 category-first):
  PRIMARY:   f_def_cat=3.2, f_def_osm=2.8, f_def_web=2.6
  SUPPORTING: f_def_name=1.4 (demoted — cannot solo-accept)
  PENALTY:   f_name_only_primary=-3.0 (blocks name-only accepts)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from app.relevance.concepts import ConceptCard
from app.relevance.features import RelevanceFeatures

_WEIGHTS_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "relevance_weights.yaml"

_DEFAULT_CONFIG: dict[str, Any] = {
    "bias": -0.8,
    "weights": {
        "f_def_cat": 3.2,
        "f_def_osm": 2.8,
        "f_def_web": 2.6,
        "f_def_name": 1.4,
        "f_name_only_primary": -0.5,
        "f_sup_count": 0.8,
        "f_host_cat": 0.2,
        "f_nonev_only": -2.8,
        "f_cat_conf": 0.4,
        "f_src_agree": 0.5,
        "f_sem_pos": 1.0,
        "f_sem_neg": -1.4,
        "f_sem_margin": 1.4,
        "f_ce": 2.2,
    },
    "thresholds": {
        "tau_hi": 0.75,
        "tau_lo": 0.35,
        "require_defining_signal": True,
    },
}

if _WEIGHTS_PATH.exists():
    try:
        with open(_WEIGHTS_PATH, "r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f)
            if isinstance(loaded, dict):
                _DEFAULT_CONFIG.update(loaded)
    except Exception:
        pass


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(min(x, 15.0), -15.0)))


@dataclass
class ScoreResult:
    p: float
    raw_logit: float
    outcome: str   # 'accepted' | 'rejected' | 'uncertain'
    has_defining_signal: bool
    has_primary_signal: bool   # v2.2: cat/osm/web only — name excluded
    top_reasons: list[dict[str, Any]]
    scorer_version: str = "v2.2-category-first"


def score_evidence(
    features: RelevanceFeatures,
    card: ConceptCard,
    custom_weights: dict[str, float] | None = None,
) -> ScoreResult:
    """Compute calibrated relevance probability p and stage outcome.

    v2.2 change: has_primary_signal excludes f_def_name. A lead with only a
    name-token match (f_def_name=1, f_def_cat=0, f_def_osm=0, f_def_web=0)
    is penalised by f_name_only_primary=-3.0 and routed to review/rejected,
    never accepted.
    """
    weights = custom_weights or _DEFAULT_CONFIG.get("weights", {})
    bias = _DEFAULT_CONFIG.get("bias", -0.8)

    feat_dict = features.to_dict()
    contributions: list[tuple[str, float]] = []

    logit = bias
    for fname, val in feat_dict.items():
        w = weights.get(fname, 0.0)
        contrib = w * val
        logit += contrib
        if abs(contrib) > 0.05:
            contributions.append((fname, contrib))

    p = _sigmoid(logit)

    # ── has_defining_signal: any of the four signal types fired ──────────────
    def_signal_sum = (
        features.f_def_name + features.f_def_cat + features.f_def_osm + features.f_def_web
    )
    has_defining_signal = def_signal_sum >= 1.0

    # ── has_primary_signal: category/OSM/web only — name excluded (v2.2) ────
    # Name alone is supporting. A lead needs at least one primary signal to
    # be accepted without cross-encoder / LLM rescue.
    has_primary_signal = (
        features.f_def_cat >= 1.0
        or features.f_def_osm >= 1.0
        or features.f_def_web >= 1.0
    )

    tau_hi = card.decision.tau_hi or 0.75
    tau_lo = card.decision.tau_lo or 0.35
    require_def = card.decision.require_defining_signal

    # Top contributing features for UI chips
    contributions.sort(key=lambda x: abs(x[1]), reverse=True)
    top_reasons: list[dict[str, Any]] = []
    for fname, contrib in contributions[:3]:
        top_reasons.append({
            "feature": fname,
            "weight": round(contrib, 3),
            "value": round(feat_dict.get(fname, 0.0), 3),
        })

    # ── Decision logic ────────────────────────────────────────────────────────
    if p >= tau_hi:
        if require_def and not has_defining_signal:
            # No signal at all → uncertain (cross-encoder / LLM rescue)
            outcome = "uncertain"
        elif require_def and not has_primary_signal:
            # Name-only match → uncertain (cannot accept on name alone in v2.2)
            # The f_name_only_primary penalty should already push p below tau_hi,
            # but this is a belt-and-suspenders structural guard.
            outcome = "uncertain"
        else:
            outcome = "accepted"
    elif p < tau_lo:
        outcome = "rejected"
    else:
        outcome = "uncertain"

    return ScoreResult(
        p=round(p, 4),
        raw_logit=round(logit, 4),
        outcome=outcome,
        has_defining_signal=has_defining_signal,
        has_primary_signal=has_primary_signal,
        top_reasons=top_reasons,
    )
