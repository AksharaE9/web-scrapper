"""
Relevance Cascade Engine — LeadCore Zero v2.2 Orchestrator

Executes the explainable, evidence-based cascade:
  R0: Tokenize & Normalizer
  R1: Hard Gates (geo, closed, exclude, veto, incompatible)
  R2: Feature Extraction
  R3: Semantic Retrieval (BAAI/bge-small-en-v1.5)
  R4: Evidence Scorer (Calibrated logistic + structural defining signal check)
  R5: Cross-Encoder Reranking (ms-marco-MiniLM-L-6-v2)
  R6: Small-LLM Adjudicator (Ollama with literal quote validation)

v2.2 changes:
  - category-first scoring (see scorer.py)
  - uncertain-path short-circuit: when LLM_ENABLED=false and scorer returns
    uncertain, we immediately return outcome='review' without wasting time on
    R5/R6 that will also return uncertain.
  - name-only match is never accepted; always routed to review or rejected
    via the f_name_only_primary penalty + has_primary_signal check.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.relevance.adjudicate import adjudicate_candidate
from app.relevance.concepts import ConceptCard, resolve_concept
from app.relevance.explain import format_reason_chip
from app.relevance.features import RelevanceFeatures, extract_features
from app.relevance.gates import check_hard_gates
from app.relevance.rerank import rerank_candidate
from app.relevance.scorer import ScoreResult, score_evidence
from app.relevance.semantic import compute_semantic_scores
from app.relevance.tokenize import TokenizedProfile, tokenize_profile
from app.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class RelevanceDecision:
    outcome: str   # 'accepted' | 'review' | 'rejected'
    p: float
    stage: str     # 'hard_gates' | 'scorer' | 'cross_encoder' | 'web' | 'llm' | 'review_band'
    features: dict[str, float] = field(default_factory=dict)
    reasons: list[dict[str, Any]] = field(default_factory=list)
    reason_code: str | None = None
    concept_id: str = ""
    concept_version: int = 1
    scorer_version: str = "v2.2"
    is_edge_case: bool = False


async def evaluate_candidate(
    name: str,
    keyword: str,
    lon: float,
    lat: float,
    categories: list[str] | None = None,
    brand: str | None = None,
    osm_tags: list[str] | None = None,
    web_meta: str | None = None,
    boundary_wkt: str | None = None,
    operating_status: str | None = None,
    user_excludes: list[str] | None = None,
    source_confidence: float | None = None,
    source_lineage: list[str] | None = None,
    card: ConceptCard | None = None,
    llm_budget_remaining: int = 60,
    # v2.2: when True, all candidates are forced to review (synthesized card path)
    force_review: bool = False,
) -> RelevanceDecision:
    """Evaluate a single candidate business through the full relevance cascade."""
    # Resolve Concept Card
    concept_card = card or resolve_concept(keyword)

    # ── R0: Tokenization & Normalization ─────────────────────────────────
    profile = tokenize_profile(
        name=name,
        categories=categories,
        brand=brand,
        osm_tags=osm_tags,
        web_meta=web_meta,
    )

    # ── R1: Hard Gates ───────────────────────────────────────────────────
    gate_res = check_hard_gates(
        profile=profile,
        card=concept_card,
        lon=lon,
        lat=lat,
        boundary_wkt=boundary_wkt,
        operating_status=operating_status,
        user_excludes=user_excludes,
        brand=brand,
        raw_categories=categories,
    )

    if not gate_res.passed:
        chip = format_reason_chip(gate_res.reason_code or "veto", gate_res.detail)
        return RelevanceDecision(
            outcome="rejected",
            p=0.0,
            stage="hard_gates",
            features={},
            reasons=[chip],
            reason_code=gate_res.reason_code,
            concept_id=concept_card.concept_id,
            concept_version=concept_card.version,
            is_edge_case=gate_res.is_edge_case,
        )

    # ── Synthesized card fast-path ───────────────────────────────────────
    # A synthesized card has no curated categories, so we cannot trust any
    # scoring outcome. Route directly to review without wasting compute.
    if force_review or concept_card.is_synthesized:
        return RelevanceDecision(
            outcome="review",
            p=0.5,
            stage="review_band",
            features={},
            reasons=[format_reason_chip("concept_missing", detail=f"No reviewed card for '{keyword}'")],
            reason_code="concept_missing",
            concept_id=concept_card.concept_id,
            concept_version=concept_card.version,
            is_edge_case=gate_res.is_edge_case,
        )

    # ── R3: Semantic Retrieval (Bi-Encoder) ───────────────────────────────
    sem_pos, sem_neg, sem_margin = compute_semantic_scores(
        profile_text=profile.profile_text,
        concept_id=concept_card.concept_id,
    )

    # ── R2: Feature Extraction ───────────────────────────────────────────
    features = extract_features(
        profile=profile,
        card=concept_card,
        raw_categories=categories,
        osm_tags=osm_tags,
        source_confidence=source_confidence,
        source_lineage=source_lineage,
        sem_pos=sem_pos,
        sem_neg=sem_neg,
        ce_score=0.5,
    )

    # ── R4: Evidence Scorer ──────────────────────────────────────────────
    score_res = score_evidence(features, concept_card)

    chips: list[dict[str, Any]] = []
    # Add top feature chips
    for r in score_res.top_reasons:
        chips.append(format_reason_chip(r["feature"], detail=None, weight=r["weight"]))

    if score_res.outcome == "accepted":
        return RelevanceDecision(
            outcome="accepted",
            p=score_res.p,
            stage="scorer",
            features=features.to_dict(),
            reasons=chips,
            reason_code=None,
            concept_id=concept_card.concept_id,
            concept_version=concept_card.version,
            is_edge_case=gate_res.is_edge_case,
        )
    elif score_res.outcome == "rejected":
        # Recall rescue check: if rejected as no-evidence only but strong semantic margin
        if sem_margin >= 0.20 and features.f_nonev_only == 0:
            chips.append(format_reason_chip("bi_encoder", detail="Rescued by semantic margin", weight=sem_margin))
            # Proceed to uncertain band rather than immediate rejection
        else:
            chips.append(format_reason_chip("low_evidence", detail="Insufficient defining signals"))
            return RelevanceDecision(
                outcome="rejected",
                p=score_res.p,
                stage="scorer",
                features=features.to_dict(),
                reasons=chips,
                reason_code="low_evidence",
                concept_id=concept_card.concept_id,
                concept_version=concept_card.version,
                is_edge_case=gate_res.is_edge_case,
            )

    # ── Uncertain-path short-circuit (v2.2) ──────────────────────────────
    # When LLM is disabled and the scorer returned uncertain (which includes
    # all name-only matches), route directly to review rather than wasting
    # compute on R5/R6 that will also return uncertain/review.
    # This is the fix for the "Accepted 19 / Review 0 / Rejected 0" bug signature.
    if not settings.llm_enabled:
        reason_detail = (
            "Name-only match — needs category/web corroboration"
            if features.f_name_only_primary == 1.0
            else "Borderline score — LLM disabled, routed to review"
        )
        chips.append(format_reason_chip("review_band", detail=reason_detail))
        return RelevanceDecision(
            outcome="review",
            p=score_res.p,
            stage="review_band",
            features=features.to_dict(),
            reasons=chips,
            reason_code="uncertain_llm_disabled",
            concept_id=concept_card.concept_id,
            concept_version=concept_card.version,
            is_edge_case=gate_res.is_edge_case,
        )

    # ── R5: Cross-Encoder Reranker (Uncertain Band) ───────────────────────
    ce_res = rerank_candidate(
        profile=profile,
        card=concept_card,
        has_defining_signal=score_res.has_defining_signal,
    )
    features.f_ce = ce_res.ce_score
    chips.append(format_reason_chip("cross_encoder", weight=ce_res.ce_score))

    if ce_res.outcome == "accepted":
        # Cross-encoder can only accept if there is also a primary signal
        # (name-only still cannot reach accepted via cross-encoder)
        if score_res.has_primary_signal:
            return RelevanceDecision(
                outcome="accepted",
                p=max(score_res.p, ce_res.ce_score),
                stage="cross_encoder",
                features=features.to_dict(),
                reasons=chips,
                reason_code=None,
                concept_id=concept_card.concept_id,
                concept_version=concept_card.version,
                is_edge_case=gate_res.is_edge_case,
            )
        else:
            # Cross-encoder accepted but no primary signal → review
            chips.append(format_reason_chip("review_band", detail="CE accepted but no primary category signal"))
            return RelevanceDecision(
                outcome="review",
                p=max(score_res.p, ce_res.ce_score),
                stage="cross_encoder",
                features=features.to_dict(),
                reasons=chips,
                reason_code="ce_accepted_no_primary",
                concept_id=concept_card.concept_id,
                concept_version=concept_card.version,
                is_edge_case=gate_res.is_edge_case,
            )
    elif ce_res.outcome == "rejected":
        return RelevanceDecision(
            outcome="rejected",
            p=min(score_res.p, ce_res.ce_score),
            stage="cross_encoder",
            features=features.to_dict(),
            reasons=chips,
            reason_code="cross_encoder_low",
            concept_id=concept_card.concept_id,
            concept_version=concept_card.version,
            is_edge_case=gate_res.is_edge_case,
        )

    # ── R6: Small-LLM Adjudicator (Last Resort) ──────────────────────────
    llm_res = await adjudicate_candidate(
        profile=profile,
        card=concept_card,
        call_budget_remaining=llm_budget_remaining,
    )
    chips.append(format_reason_chip("llm", detail=llm_res.reason))

    # LLM can only accept if there is a primary signal (name-only guard)
    llm_outcome = llm_res.outcome
    if llm_outcome == "accepted" and not score_res.has_primary_signal:
        llm_outcome = "review"
        chips.append(format_reason_chip("review_band", detail="LLM accepted but no primary category signal"))

    return RelevanceDecision(
        outcome=llm_outcome,
        p=score_res.p,
        stage="llm" if llm_res.verdict != "unsure" else "review_band",
        features=features.to_dict(),
        reasons=chips,
        reason_code=None if llm_outcome == "accepted" else ("llm_rejected" if llm_outcome == "rejected" else "uncertain"),
        concept_id=concept_card.concept_id,
        concept_version=concept_card.version,
        is_edge_case=gate_res.is_edge_case,
    )
