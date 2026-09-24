"""
R0 — Tokenizer and Normalizer for Indian Business Names & Profiles

Provides deterministic, high-speed, keyless text normalization:
  1. Unicode NFKC normalization and Indic script transliteration
  2. Map-icon glyph stripping & whitespace collapsing
  3. Word-boundary tokenization with compound splitting
  4. Transliteration variant folding (variants.yaml + RapidFuzz fallback)
  5. Non-evidence stopword classification (non_evidence.yaml)
  6. Structured TokenizedProfile construction
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from rapidfuzz.distance import JaroWinkler

# Load Lexicons
_LEXICON_DIR = Path(__file__).resolve().parent.parent.parent / "config" / "lexicon"

_VARIANTS_PATH = _LEXICON_DIR / "variants.yaml"
_NON_EVIDENCE_PATH = _LEXICON_DIR / "non_evidence.yaml"

_VARIANT_MAP: dict[str, str] = {}
if _VARIANTS_PATH.exists():
    try:
        with open(_VARIANTS_PATH, "r", encoding="utf-8") as f:
            v_data = yaml.safe_load(f) or {}
        for canonical, aliases in v_data.items():
            _VARIANT_MAP[canonical.lower()] = canonical.lower()
            if isinstance(aliases, list):
                for a in aliases:
                    _VARIANT_MAP[str(a).lower()] = canonical.lower()
    except Exception:
        pass

_NON_EVIDENCE_TOKENS: set[str] = set()
if _NON_EVIDENCE_PATH.exists():
    try:
        with open(_NON_EVIDENCE_PATH, "r", encoding="utf-8") as f:
            ne_data = yaml.safe_load(f) or {}
        for group, words in ne_data.items():
            if isinstance(words, list):
                for w in words:
                    _NON_EVIDENCE_TOKENS.add(str(w).lower().strip())
    except Exception:
        pass


# Indic script transliteration helper
def _transliterate_indic_text(text: str) -> str:
    """Detect and transliterate Indic scripts (Devanagari, Kannada, Telugu, Tamil, Malayalam) to Latin."""
    try:
        from indic_transliteration import sanscript
        from indic_transliteration.sanscript import SchemeMap, SCHEMES, transliterate

        # Check for non-ASCII characters
        has_indic = any(ord(c) > 0x0900 and ord(c) < 0x0DFF for c in text)
        if not has_indic:
            return text

        # Detect specific script ranges
        detected_scheme = None
        for char in text:
            cp = ord(char)
            if 0x0900 <= cp <= 0x097F:
                detected_scheme = sanscript.DEVANAGARI
                break
            elif 0x0C80 <= cp <= 0x0CFF:
                detected_scheme = sanscript.KANNADA
                break
            elif 0x0C00 <= cp <= 0x0C7F:
                detected_scheme = sanscript.TELUGU
                break
            elif 0x0B80 <= cp <= 0x0BFF:
                detected_scheme = sanscript.TAMIL
                break
            elif 0x0D00 <= cp <= 0x0D7F:
                detected_scheme = sanscript.MALAYALAM
                break

        if detected_scheme:
            translit = transliterate(text, detected_scheme, sanscript.ITRANS)
            return f"{text} {translit}"
    except Exception:
        pass
    return text


def sanitize_raw_text(text: str) -> str:
    """NFKC normalize, transliterate Indic text, remove soft hyphens and map glyphs."""
    if not text:
        return ""
    # Unicode NFKC
    norm = unicodedata.normalize("NFKC", str(text))
    # Transliterate Indic characters
    norm = _transliterate_indic_text(norm)
    # Strip map icon symbols / emojis / soft hyphens
    norm = re.sub(r"[\xad\u200b-\u200f\ufeff]", "", norm)
    # Replace punctuation with spaces
    norm = re.sub(r"[^\w\s]", " ", norm)
    # Collapse whitespace
    norm = re.sub(r"\s+", " ", norm).strip().lower()
    return norm


def _split_compound_word(word: str, known_lexicon: set[str]) -> list[str]:
    """Greedy longest-match compound splitting for joined tokens (e.g. poojastores -> pooja stores)."""
    if len(word) < 7:
        return [word]

    # Check if word is already in lexicon or is a known variant
    if word in known_lexicon or word in _VARIANT_MAP:
        return [word]

    parts: list[str] = []
    start = 0
    max_parts = 3

    while start < len(word) and len(parts) < max_parts:
        matched = None
        # Try longest match from right
        for end in range(len(word), start + 2, -1):
            sub = word[start:end]
            if sub in known_lexicon or sub in _VARIANT_MAP or sub in _NON_EVIDENCE_TOKENS:
                matched = sub
                start = end
                break
        if matched:
            parts.append(matched)
        else:
            parts.append(word[start:])
            break

    return parts if parts else [word]


def canonicalize_token(token: str) -> str:
    """Map token to canonical form using variants dictionary or RapidFuzz Jaro-Winkler >= 0.92."""
    tok = token.lower().strip()
    if not tok:
        return ""

    if tok in _VARIANT_MAP:
        return _VARIANT_MAP[tok]

    # RapidFuzz fallback for words of length >= 5
    if len(tok) >= 5:
        best_match = None
        best_sim = 0.0
        for variant_key, canonical in _VARIANT_MAP.items():
            sim = JaroWinkler.similarity(tok, variant_key)
            if sim > best_sim:
                best_sim = sim
                best_match = canonical
        if best_sim >= 0.92 and best_match:
            return best_match

    return tok


def is_non_evidence_token(token: str) -> bool:
    """Return True if token belongs to honorifics, generic deities, or generic suffixes."""
    tok = token.lower().strip()
    return tok in _NON_EVIDENCE_TOKENS


@dataclass
class TokenizedProfile:
    raw_name: str
    clean_name: str
    name_tokens: list[str] = field(default_factory=list)
    name_bigrams: list[str] = field(default_factory=list)
    evidence_tokens: set[str] = field(default_factory=set)
    non_evidence_tokens: set[str] = field(default_factory=set)
    category_tokens: set[str] = field(default_factory=set)
    brand_tokens: set[str] = field(default_factory=set)
    web_tokens: set[str] = field(default_factory=set)
    profile_text: str = ""


def tokenize_profile(
    name: str,
    categories: list[str] | None = None,
    brand: str | None = None,
    osm_tags: list[str] | None = None,
    web_meta: str | None = None,
) -> TokenizedProfile:
    """Construct a full TokenizedProfile for a candidate business."""
    clean_name = sanitize_raw_text(name)
    raw_tokens = [t for t in re.split(r"\s+", clean_name) if t]

    known_words = set(_VARIANT_MAP.keys()).union(_NON_EVIDENCE_TOKENS)

    expanded_tokens: list[str] = []
    for t in raw_tokens:
        splits = _split_compound_word(t, known_words)
        expanded_tokens.extend(splits)

    canonical_tokens = [canonicalize_token(t) for t in expanded_tokens if t]

    evidence: set[str] = set()
    non_evidence: set[str] = set()

    for raw_t, can_t in zip(expanded_tokens, canonical_tokens):
        if is_non_evidence_token(raw_t) or is_non_evidence_token(can_t):
            non_evidence.add(raw_t)
            non_evidence.add(can_t)
        else:
            evidence.add(can_t)

    # Bigrams
    bigrams = [
        f"{canonical_tokens[i]} {canonical_tokens[i+1]}"
        for i in range(len(canonical_tokens) - 1)
    ]

    # Category tokens
    cat_tokens: set[str] = set()
    if categories:
        for cat in categories:
            clean_c = sanitize_raw_text(cat)
            for c_tok in re.split(r"\s+", clean_c):
                if c_tok:
                    cat_tokens.add(canonicalize_token(c_tok))

    # Brand tokens
    b_tokens: set[str] = set()
    if brand:
        clean_b = sanitize_raw_text(brand)
        for b_tok in re.split(r"\s+", clean_b):
            if b_tok:
                b_tokens.add(canonicalize_token(b_tok))

    # Web tokens
    w_tokens: set[str] = set()
    if web_meta:
        clean_w = sanitize_raw_text(web_meta)
        for w_tok in re.split(r"\s+", clean_w):
            if w_tok:
                w_tokens.add(canonicalize_token(w_tok))

    # Build embedding profile text:
    # {name} | categories: {cats}; osm: {tags} | brand: {brand} | web: {meta}
    cat_str = "; ".join(categories) if categories else ""
    osm_str = "; ".join(osm_tags) if osm_tags else ""
    profile_parts = [f"{name}"]
    if cat_str or osm_str:
        profile_parts.append(f"categories: {cat_str}; osm: {osm_str}".strip("; "))
    if brand:
        profile_parts.append(f"brand: {brand}")
    if web_meta:
        profile_parts.append(f"web: {web_meta[:300]}")

    profile_text = " | ".join(profile_parts)

    return TokenizedProfile(
        raw_name=name,
        clean_name=clean_name,
        name_tokens=canonical_tokens,
        name_bigrams=bigrams,
        evidence_tokens=evidence,
        non_evidence_tokens=non_evidence,
        category_tokens=cat_tokens,
        brand_tokens=b_tokens,
        web_tokens=w_tokens,
        profile_text=profile_text,
    )
