"""
R5 — Cross-Encoder Reranker (Uncertain Band Only)

Uses fastembed cross-encoder (Xenova/ms-marco-MiniLM-L-6-v2).
Computes deep query-document relevance between ConceptCard definition / question and candidate profile.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any

from app.relevance.concepts import ConceptCard
from app.relevance.tokenize import TokenizedProfile

logger = logging.getLogger(__name__)

_CROSS_ENCODER: Any = None


def get_cross_encoder() -> Any:
    """Return TextCrossEncoder singleton."""
    global _CROSS_ENCODER
    if _CROSS_ENCODER is None:
        try:
            from fastembed.rerank.cross_encoder import TextCrossEncoder
            _CROSS_ENCODER = TextCrossEncoder("Xenova/ms-marco-MiniLM-L-6-v2")
        except Exception as e:
            logger.warning(f"TextCrossEncoder initialization deferred: {e}")
            _CROSS_ENCODER = None
    return _CROSS_ENCODER


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(min(x, 15.0), -15.0)))


def _format_query(card: ConceptCard) -> str:
    primary = card.labels[0] if card.labels else card.concept_id.replace("_", " ")
    aliases = " ".join(card.labels[1:4]) if len(card.labels) > 1 else ""
    return f"{primary} {aliases}".strip()


def _format_document(profile: TokenizedProfile) -> str:
    cats = ", ".join(profile.category_tokens) if profile.category_tokens else "unspecified"
    return f"{profile.raw_name}. Categories: {cats}. {profile.profile_text}".strip()


@dataclass
class RerankResult:
    ce_score: float
    outcome: str   # 'accepted' | 'rejected' | 'uncertain'


def rerank_candidate(
    profile: TokenizedProfile,
    card: ConceptCard,
    has_defining_signal: bool = False,
) -> RerankResult:
    """Rerank an uncertain candidate profile against ConceptCard query."""
    encoder = get_cross_encoder()
    if not encoder:
        return RerankResult(ce_score=0.5, outcome="uncertain")

    query = _format_query(card)
    doc = _format_document(profile)

    try:
        raw_results = list(encoder.rerank(query, [doc]))
        if raw_results:
            first = raw_results[0]
            raw_score = float(first.score) if hasattr(first, "score") else float(first)
            ce_score = _sigmoid(raw_score)
        else:
            ce_score = 0.5
    except Exception as e:
        logger.warning(f"Cross-encoder rerank error: {e}")
        ce_score = 0.5

    tau_hi = card.decision.tau_hi if hasattr(card, "decision") and card.decision else 0.75
    tau_lo = card.decision.tau_lo if hasattr(card, "decision") and card.decision else 0.35

    if ce_score >= tau_hi and has_defining_signal:
        outcome = "accepted"
    elif ce_score <= tau_lo:
        outcome = "rejected"
    else:
        outcome = "uncertain"

    return RerankResult(ce_score=round(ce_score, 4), outcome=outcome)
