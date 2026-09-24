"""
app/relevance/fusion.py — Reciprocal Rank Fusion (RRF) combining Lexical and Dense Semantic retrieval.

Formula:
  RRF(d) = Σ_{m ∈ {lexical, dense}} 1 / (k + rank_m(d))
with k = 60 by default.
"""

from __future__ import annotations


def reciprocal_rank_fusion(
    lexical_scores: list[float],
    dense_scores: list[float],
    k: int = 60,
) -> list[float]:
    """
    Compute RRF fusion scores given parallel lists of lexical and dense scores for N candidates.
    Returns normalized fusion scores in [0, 1].
    """
    n = len(lexical_scores)
    if n == 0:
        return []

    # Sort indices by score descending to determine ranks (1-based)
    lex_ranks = {idx: rank + 1 for rank, idx in enumerate(sorted(range(n), key=lambda i: lexical_scores[i], reverse=True))}
    dense_ranks = {idx: rank + 1 for rank, idx in enumerate(sorted(range(n), key=lambda i: dense_scores[i], reverse=True))}

    rrf_raw = []
    for i in range(n):
        r_lex = lex_ranks[i]
        r_dense = dense_ranks[i]
        score = (1.0 / (k + r_lex)) + (1.0 / (k + r_dense))
        rrf_raw.append(score)

    max_score = (2.0 / (k + 1))
    return [min(1.0, s / max_score) for s in rrf_raw]
