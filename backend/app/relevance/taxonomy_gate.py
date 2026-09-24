"""
R0.5 — Taxonomy Gate

Three-verdict gate that runs BEFORE feature extraction.
Cost: ~0ms (no embeddings, pure set intersection).

Verdict semantics:
  ACCEPT_CANDIDATE — at least one defining category matched;
                     proceed to scorer, shortcut accepted if scorer agrees.
  REJECT           — incompatible category matched with no defining override;
                     immediate rejection, never scored.
  UNCERTAIN        — no category evidence found (may still pass via
                     lexical/semantic stages); proceed normally.

Design principles:
  - UNCERTAIN ≠ REJECT. Missing category data preserves recall.
  - Token-based matching (not substring) prevents shop→gift_shop false rejects.
  - Defining signal always overrides an incompatible category signal.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from app.relevance.concepts import ConceptCard


class TaxonomyVerdict(str, Enum):
    ACCEPT_CANDIDATE = "accept_candidate"
    REJECT = "reject"
    UNCERTAIN = "uncertain"


@dataclass
class TaxonomyResult:
    verdict: TaxonomyVerdict
    matched_category: str | None = None    # which category triggered the verdict
    reason: str | None = None              # human-readable description


def _tokenize_category(cat: str) -> set[str]:
    """
    Split a category string into atomic tokens.

    Examples:
      "tourism=hotel"          -> {"tourism", "hotel"}
      "gift_shop"              -> {"gift", "shop"}
      "Travel > Lodging > Hotel" -> {"travel", "lodging", "hotel"}
      "professional_services" -> {"professional", "services"}
    """
    # Lowercase and split on word boundaries: =, _, -, /, >, ., space
    parts = re.split(r"[=_\-/>\.\s]+", cat.lower())
    return {p.strip() for p in parts if p.strip()}


def _tokens_from_list(categories: list[str]) -> list[tuple[str, set[str]]]:
    """Return (original, tokenized) pairs."""
    return [(c, _tokenize_category(c)) for c in categories if c]


def gate(
    raw_categories: list[str] | None,
    card: ConceptCard,
) -> TaxonomyResult:
    """
    Evaluate candidate categories against the ConceptCard taxonomy.

    Args:
        raw_categories: Category strings from Overture taxonomy, OSM tags, etc.
        card:           ConceptCard for the keyword being searched.

    Returns:
        TaxonomyResult with verdict and human reason.
    """
    if not raw_categories:
        return TaxonomyResult(
            verdict=TaxonomyVerdict.UNCERTAIN,
            reason="no category data available",
        )

    candidate_tokens = _tokens_from_list(raw_categories)

    # Build tokenized lists from card
    defining_card_tokens = _tokens_from_list(card.categories.defining)
    host_card_tokens = _tokens_from_list(card.categories.host)
    incompatible_card_tokens = _tokens_from_list(card.categories.incompatible)

    # ── Step 1: Check defining categories ──────────────────────────────────────
    # A candidate category MATCHES a defining card category when the card's token
    # set is a SUBSET of the candidate's tokens.
    # Example: card defining = "hotel" (tokens: {"hotel"})
    #          candidate = "tourism=hotel" (tokens: {"tourism", "hotel"}) → MATCH
    #          candidate = "hotel_management" would also match — acceptable.
    # Reject the SUBSTRING approach: "shop" ⊄ {"gift", "shop"} when "shop" ∈ {"shop"}
    # but "gift_shop" tokens {"gift", "shop"} do NOT subset {"shop"} — CORRECT.
    for cand_raw, cand_toks in candidate_tokens:
        for card_raw, card_toks in defining_card_tokens:
            if card_toks and card_toks.issubset(cand_toks):
                return TaxonomyResult(
                    verdict=TaxonomyVerdict.ACCEPT_CANDIDATE,
                    matched_category=cand_raw,
                    reason=f"listed as '{cand_raw}' (matches defining category '{card_raw}')",
                )

    # ── Step 2: Check incompatible categories ──────────────────────────────────
    # Incompatible: if ANY candidate token-set is a subset of an incompatible token-set
    # (or vice-versa, i.e. any overlap with the full incompatible term), reject.
    # But only if NO defining signal was found above.
    for cand_raw, cand_toks in candidate_tokens:
        for card_raw, card_toks in incompatible_card_tokens:
            if card_toks and card_toks.issubset(cand_toks):
                return TaxonomyResult(
                    verdict=TaxonomyVerdict.REJECT,
                    matched_category=cand_raw,
                    reason=f"listed as '{cand_raw}' which is incompatible (matches '{card_raw}')",
                )

    # ── Step 3: Host categories → UNCERTAIN (not rejected) ────────────────────
    for cand_raw, cand_toks in candidate_tokens:
        for card_raw, card_toks in host_card_tokens:
            if card_toks and card_toks.issubset(cand_toks):
                return TaxonomyResult(
                    verdict=TaxonomyVerdict.UNCERTAIN,
                    matched_category=cand_raw,
                    reason=f"listed as '{cand_raw}' (host category — needs corroboration)",
                )

    # ── Step 4: No match → UNCERTAIN ──────────────────────────────────────────
    return TaxonomyResult(
        verdict=TaxonomyVerdict.UNCERTAIN,
        reason="no matching taxonomy category found",
    )
