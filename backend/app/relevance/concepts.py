"""
LeadCore Zero — Concept Cards Engine & 6-Stage Resolution (FOUNDRY-1.0)

Schema, resolution, disk/db loading, aliases, taxonomy derivation, and validation.
Strict contract: resolve_concept(keyword) NEVER returns empty or fails under any input.
Zero LLM calls on the request path (sub-10ms deterministic resolution).
"""

from __future__ import annotations

import difflib
import json
import logging
import re
import unicodedata
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

from app.relevance.tokenize import sanitize_raw_text, canonicalize_token, is_non_evidence_token
from app.taxonomy.foundry import get_taxonomy_spine, normalize_text

logger = logging.getLogger(__name__)

CONCEPTS_DIR = Path(__file__).resolve().parent.parent.parent / "config" / "concepts"


class SignalConfig(BaseModel):
    defining_terms: dict[str, list[str]] = Field(default_factory=lambda: {"strong": []})
    supporting_terms: dict[str, list[str]] = Field(default_factory=lambda: {"medium": []})
    non_evidence: str = "inherit"


class CategoryConfig(BaseModel):
    defining: list[str] = Field(default_factory=list)
    host: list[str] = Field(default_factory=list)
    incompatible: list[str] = Field(default_factory=list)


class BrandConfig(BaseModel):
    incompatible: list[str] = Field(default_factory=list)


class PrototypeConfig(BaseModel):
    positive_ids: list[str] = Field(default_factory=list)
    negative_ids: list[str] = Field(default_factory=list)


class DecisionConfig(BaseModel):
    require_defining_signal: bool = True
    tau_hi: float = 0.75
    tau_lo: float = 0.35


class ConceptCard(BaseModel):
    concept_id: str
    version: int = 1
    labels: list[str] = Field(default_factory=list)
    definition: str
    signals: SignalConfig = Field(default_factory=SignalConfig)
    categories: CategoryConfig = Field(default_factory=CategoryConfig)
    veto_terms: list[str] = Field(default_factory=list)
    brands: BrandConfig = Field(default_factory=BrandConfig)
    prototypes: PrototypeConfig = Field(default_factory=PrototypeConfig)
    decision: DecisionConfig = Field(default_factory=DecisionConfig)

    # ── Search & Extraction Metadata (Unified from rules) ─────────────────────
    overture_basic_categories: list[str] = Field(default_factory=list)
    overture_taxonomy_paths: list[str] = Field(default_factory=list)
    osm_tags: list[str] = Field(default_factory=list)
    name_patterns: list[str] = Field(default_factory=list)

    # ── Provenance & Confidence Contract ──────────────────────────────────────
    provenance: Literal["seeded", "alias", "fuzzy", "retrieved", "derived", "unresolved"] = "seeded"
    confidence: float = 1.0
    did_you_mean: list[str] | None = None
    needs_review: bool = False

    # Backwards compatibility properties
    is_synthesized: bool = Field(default=False)
    is_derived: bool = Field(default=False)

    def with_provenance(
        self,
        provenance: Literal["seeded", "alias", "fuzzy", "retrieved", "derived", "unresolved"],
        confidence: float | None = None,
        did_you_mean: list[str] | None = None,
        needs_review: bool | None = None,
    ) -> ConceptCard:
        copy_card = self.model_copy(deep=True)
        copy_card.provenance = provenance
        if confidence is not None:
            copy_card.confidence = confidence
        if did_you_mean is not None:
            copy_card.did_you_mean = did_you_mean
        if needs_review is not None:
            copy_card.needs_review = needs_review
        else:
            copy_card.needs_review = provenance in ("derived", "unresolved")
        copy_card.is_derived = (provenance == "derived")
        copy_card.is_synthesized = (provenance == "unresolved")
        return copy_card

    def get_strong_defining_terms(self) -> set[str]:
        terms = set()
        for t in self.signals.defining_terms.get("strong", []):
            tok = canonicalize_token(sanitize_raw_text(t))
            if tok and not is_non_evidence_token(tok):
                terms.add(tok)
                cleaned = sanitize_raw_text(t)
                if " " in cleaned:
                    terms.add(cleaned)
        return terms

    def get_supporting_terms(self) -> set[str]:
        terms = set()
        for t in self.signals.supporting_terms.get("medium", []):
            tok = canonicalize_token(sanitize_raw_text(t))
            if tok and not is_non_evidence_token(tok):
                terms.add(tok)
                cleaned = sanitize_raw_text(t)
                if " " in cleaned:
                    terms.add(cleaned)
        return terms

    def get_veto_terms(self) -> set[str]:
        terms = set()
        for t in self.veto_terms:
            cleaned = sanitize_raw_text(t)
            if cleaned:
                terms.add(cleaned)
                for part in cleaned.split():
                    terms.add(canonicalize_token(part))
        return terms


# ── Global Cache & Catalog Indices ───────────────────────────────────────────
_DISK_CARDS_CACHE: dict[str, ConceptCard] = {}
_ALIAS_INDEX: dict[str, str] = {}  # alias_norm -> concept_id
_CARD_TOKENS_INDEX: dict[str, set[str]] = {}  # cid -> set of tokens
_INDEX_BUILT: bool = False


def _stem_keyword(kw: str) -> str:
    s = kw.strip().lower()
    if s.endswith("ies"):
        s = s[:-3] + "y"
    elif s.endswith("es") and not s.endswith("ses") and not s.endswith("ches") and not s.endswith("shes"):
        s = s[:-2]
    elif s.endswith("s") and not s.endswith("ss"):
        s = s[:-1]
    return s


def _validate_card(card: ConceptCard) -> None:
    strong = card.signals.defining_terms.get("strong", [])
    filtered_strong = []
    for term in strong:
        clean = sanitize_raw_text(term)
        if not is_non_evidence_token(clean) and not is_non_evidence_token(canonicalize_token(clean)):
            filtered_strong.append(term)
    card.signals.defining_terms["strong"] = filtered_strong or [card.concept_id.replace("_", " ")]


def load_all_cards() -> dict[str, ConceptCard]:
    """Load and index all cards from config/concepts/."""
    global _DISK_CARDS_CACHE, _ALIAS_INDEX, _CARD_TOKENS_INDEX, _INDEX_BUILT
    if _INDEX_BUILT and _DISK_CARDS_CACHE:
        return _DISK_CARDS_CACHE

    cards: dict[str, ConceptCard] = {}
    alias_map: dict[str, str] = {}
    tokens_map: dict[str, set[str]] = {}

    if CONCEPTS_DIR.exists():
        for yaml_file in CONCEPTS_DIR.glob("*.yaml"):
            cid = yaml_file.stem
            try:
                with open(yaml_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                card = ConceptCard(**data)
                _validate_card(card)
                cards[cid] = card

                # Build alias index
                norm_cid = normalize_text(cid.replace("_", " "))
                alias_map[norm_cid] = cid
                alias_map[_stem_keyword(norm_cid)] = cid

                card_tokens: set[str] = set()
                card_tokens.update(norm_cid.split())

                for lbl in card.labels:
                    norm_lbl = normalize_text(lbl)
                    if norm_lbl:
                        alias_map[norm_lbl] = cid
                        alias_map[_stem_keyword(norm_lbl)] = cid
                        card_tokens.update(norm_lbl.split())

                for term in card.signals.defining_terms.get("strong", []):
                    norm_term = normalize_text(term)
                    if len(norm_term) > 2:
                        alias_map.setdefault(norm_term, cid)
                        card_tokens.update(norm_term.split())

                tokens_map[cid] = card_tokens

            except Exception as e:
                logger.warning(f"Failed to load concept card {yaml_file}: {e}")

    _DISK_CARDS_CACHE = cards
    _ALIAS_INDEX = alias_map
    _CARD_TOKENS_INDEX = tokens_map
    _INDEX_BUILT = True
    return _DISK_CARDS_CACHE


def load_card_from_disk(concept_id: str) -> ConceptCard | None:
    cards = load_all_cards()
    return cards.get(concept_id)


# ── The 6-Stage Resolution Engine ─────────────────────────────────────────────

def resolve_concept(keyword: str) -> ConceptCard:
    """
    Resolve a keyword string to its matching ConceptCard following the 6-stage contract:
      Stage 1: EXACT — concept_id or primary label (provenance: seeded, confidence: 1.0)
      Stage 2: ALIAS — synonym dictionary & aliases (provenance: alias, confidence: 0.95)
      Stage 3: TRIGRAM — fuzzy typo match (provenance: fuzzy, confidence: score)
      Stage 4: HYBRID RETRIEVAL — lexical & semantic token overlap (provenance: retrieved)
      Stage 5: DERIVE FROM TAXONOMY — Overture/OSM deterministic subtree & sibling vetoes (provenance: derived)
      Stage 6: LAST RESORT — minimal structured card (provenance: unresolved)
    
    GUARANTEE: Never returns None. Never raises. Sub-10ms offline resolution.
    """
    if not keyword or not isinstance(keyword, str):
        keyword = "general store"

    raw_clean = sanitize_raw_text(keyword)
    norm = normalize_text(raw_clean)
    if not norm:
        norm = "general store"
        raw_clean = "general store"

    stemmed = _stem_keyword(norm)
    norm_underscore = norm.replace(" ", "_")
    stemmed_underscore = stemmed.replace(" ", "_")

    cards = load_all_cards()

    # ── STAGE 1 · EXACT MATCH ────────────────────────────────────────────────
    for cand in [norm_underscore, stemmed_underscore, norm, stemmed]:
        if cand in cards:
            return cards[cand].with_provenance("seeded", confidence=1.0)

    # ── STAGE 2 · ALIAS & SYNONYMS ───────────────────────────────────────────
    for cand in [norm, stemmed, raw_clean.lower()]:
        if cand in _ALIAS_INDEX and _ALIAS_INDEX[cand] in cards:
            matched_cid = _ALIAS_INDEX[cand]
            return cards[matched_cid].with_provenance("alias", confidence=0.95)

    # ── STAGE 3 · TRIGRAM / FUZZY TYPO MATCH ─────────────────────────────────
    # Only evaluate fuzzy if length > 3 and not random single characters
    if len(norm) >= 4:
        best_fuzzy_cid = None
        best_fuzzy_score = 0.0
        best_fuzzy_target = ""

        for alias_key, cid in _ALIAS_INDEX.items():
            if abs(len(norm) - len(alias_key)) > 4:
                continue
            ratio = difflib.SequenceMatcher(None, norm, alias_key).ratio()
            if ratio > best_fuzzy_score:
                best_fuzzy_score = ratio
                best_fuzzy_cid = cid
                best_fuzzy_target = alias_key

        if best_fuzzy_score >= 0.78 and best_fuzzy_cid and best_fuzzy_cid in cards:
            target_card = cards[best_fuzzy_cid]
            display_label = target_card.labels[0] if target_card.labels else best_fuzzy_target
            return target_card.with_provenance(
                "fuzzy",
                confidence=round(best_fuzzy_score, 2),
                did_you_mean=[display_label],
            )

    # ── STAGE 4 · HYBRID / TOKEN OVERLAP RETRIEVAL ───────────────────────────
    kw_tokens = {w for w in norm.split() if len(w) > 2 and not is_non_evidence_token(w)}
    if kw_tokens:
        best_hybrid_cid = None
        best_hybrid_score = 0.0

        for cid, card_tokens in _CARD_TOKENS_INDEX.items():
            overlap = len(kw_tokens & card_tokens)
            if overlap > 0:
                score = overlap / len(kw_tokens)
                if score > best_hybrid_score:
                    best_hybrid_score = score
                    best_hybrid_cid = cid

        if best_hybrid_score >= 0.75 and best_hybrid_cid and best_hybrid_cid in cards:
            return cards[best_hybrid_cid].with_provenance(
                "retrieved",
                confidence=round(best_hybrid_score, 2),
            )

    # ── STAGE 5 · DERIVE FROM TAXONOMY (Overture & Taginfo) ───────────────────
    spine = get_taxonomy_spine()
    matched_cat_id, cat_score = spine.find_matching_category(raw_clean)

    if matched_cat_id:
        cat_obj = spine.get_category(matched_cat_id)
        display_name = cat_obj.display_name if cat_obj else matched_cat_id.replace("_", " ").title()
        siblings = spine.get_siblings(matched_cat_id) if cat_obj else []

        # Build contrastive vetoes from siblings
        vetoes = [s.replace("_", " ") for s in siblings[:10]]
        tokens = [canonicalize_token(t) for t in raw_clean.split() if not is_non_evidence_token(t)]

        derived_card = ConceptCard(
            concept_id=matched_cat_id,
            version=1,
            labels=[raw_clean, display_name, matched_cat_id.replace("_", " ")],
            definition=f"Commercial enterprise categorized under {display_name} ({cat_obj.primary_hierarchy if cat_obj else matched_cat_id}).",
            signals=SignalConfig(
                defining_terms={"strong": list(dict.fromkeys(tokens + [raw_clean.lower(), display_name.lower()]))},
                supporting_terms={"medium": [s.replace("_", " ") for s in siblings[:5]]},
            ),
            categories=CategoryConfig(
                defining=[matched_cat_id, cat_obj.basic_category if cat_obj else matched_cat_id],
                host=["commercial_building", "shopping_complex", "market"],
                incompatible=siblings[:8],
            ),
            veto_terms=vetoes,
            overture_basic_categories=[cat_obj.basic_category] if cat_obj else [matched_cat_id],
            overture_taxonomy_paths=[cat_obj.primary_hierarchy] if cat_obj else [],
            osm_tags=[f"shop={matched_cat_id}", f"amenity={matched_cat_id}"],
            name_patterns=[f"\\b{re.escape(raw_clean.lower())}\\b"],
            brands=BrandConfig(incompatible=[]),
            decision=DecisionConfig(require_defining_signal=True, tau_hi=0.75, tau_lo=0.35),
            provenance="derived",
            confidence=round(cat_score, 2),
            needs_review=True,
            is_derived=True,
            is_synthesized=False,
        )
        _DISK_CARDS_CACHE[matched_cat_id] = derived_card
        _ALIAS_INDEX[norm] = matched_cat_id
        return derived_card

    # ── STAGE 6 · LAST RESORT (UNRESOLVED MINIMAL CARD) ──────────────────────
    tokens = [canonicalize_token(t) for t in raw_clean.split() if not is_non_evidence_token(t)]
    safe_cid = norm_underscore if norm_underscore else "unresolved_business"
    
    unresolved_card = ConceptCard(
        concept_id=safe_cid,
        version=1,
        labels=[raw_clean],
        definition=f"Commercial enterprise matching keyword '{raw_clean}'.",
        signals=SignalConfig(
            defining_terms={"strong": tokens or [raw_clean.lower()]},
            supporting_terms={"medium": []},
        ),
        categories=CategoryConfig(
            defining=[safe_cid],
            host=["commercial_building", "market_place"],
            incompatible=["unrelated_industry"],
        ),
        veto_terms=[],
        overture_basic_categories=[safe_cid],
        osm_tags=["shop", "amenity"],
        name_patterns=[f"\\b{re.escape(raw_clean.lower())}\\b"],
        brands=BrandConfig(incompatible=[]),
        decision=DecisionConfig(require_defining_signal=True, tau_hi=0.75, tau_lo=0.35),
        provenance="unresolved",
        confidence=0.50,
        needs_review=True,
        is_derived=False,
        is_synthesized=True,
    )
    _DISK_CARDS_CACHE[safe_cid] = unresolved_card
    _ALIAS_INDEX[norm] = safe_cid
    return unresolved_card


def derive_concept_from_taxonomy(keyword: str) -> ConceptCard:
    """Backwards-compatible bridge returning a resolved ConceptCard."""
    return resolve_concept(keyword)
