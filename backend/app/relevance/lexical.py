"""
app/relevance/lexical.py — Lexical matching (BM25 / Trigram / Exact) over Concept Cards.

Catches exact keyword tokens and transliterations that dense semantic vectors can miss.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Any
from app.relevance.concepts import ConceptCard
from app.relevance.tokenize import TokenizedProfile


def compute_trigram_set(text: str) -> set[str]:
    """Compute character 3-grams for text of length >= 3."""
    clean = text.lower().strip()
    if len(clean) < 3:
        return {clean}
    return {clean[i:i + 3] for i in range(len(clean) - 2)}


def trigram_similarity(text1: str, text2: str) -> float:
    """Jaccard similarity of character trigrams."""
    t1 = compute_trigram_set(text1)
    t2 = compute_trigram_set(text2)
    if not t1 or not t2:
        return 0.0
    intersection = len(t1 & t2)
    union = len(t1 | t2)
    return intersection / float(union) if union > 0 else 0.0


def score_lexical_bm25(
    profile: TokenizedProfile,
    card: ConceptCard,
) -> float:
    """
    Compute BM25-inspired lexical score between candidate profile and Concept Card terms.
    Strongly boosts defining terms and rewards supporting terms.
    """
    def_terms = getattr(card.signals, "defining_terms", None)
    if def_terms is None and isinstance(card.signals, dict):
        def_terms = card.signals.get("defining_terms", {})
    if isinstance(def_terms, dict):
        card_defining = set(def_terms.get("strong", []))
    else:
        card_defining = set(getattr(def_terms, "strong", []))

    sup_terms = getattr(card.signals, "supporting_terms", None)
    if sup_terms is None and isinstance(card.signals, dict):
        sup_terms = card.signals.get("supporting_terms", {})
    if isinstance(sup_terms, dict):
        card_supporting = set(sup_terms.get("medium", []))
    else:
        card_supporting = set(getattr(sup_terms, "medium", []))

    score = 0.0
    all_cand_tokens = set(profile.name_tokens) | set(profile.category_tokens) | set(profile.web_tokens)

    # 1. Defining term exact/token matches
    for def_term in card_defining:
        def_tokens = def_term.lower().split()
        if len(def_tokens) == 1:
            if def_term.lower() in all_cand_tokens:
                score += 1.0
        else:
            # Multi-word term
            if all(t in all_cand_tokens for t in def_tokens):
                score += 1.2

    # 2. Supporting term matches
    for sup_term in card_supporting:
        sup_tokens = sup_term.lower().split()
        if len(sup_tokens) == 1:
            if sup_term.lower() in all_cand_tokens:
                score += 0.35
        else:
            if all(t in all_cand_tokens for t in sup_tokens):
                score += 0.5

    # 3. Trigram fuzzy fallback on candidate name against card labels
    max_tri = 0.0
    for label in card.labels:
        sim = trigram_similarity(profile.profile_text.split("|")[0], label)
        if sim > max_tri:
            max_tri = sim
    score += max_tri * 0.4

    # Normalized score in [0, 1]
    return min(1.0, score / 2.0)
