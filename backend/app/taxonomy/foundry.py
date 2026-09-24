"""
LeadCore Zero — Concept Card Foundry & Taxonomy Spine (FOUNDRY-1.0)

Unified taxonomy engine managing:
1. Overture category hierarchy (2,354 categories across 13 L0 groups, 286 basic categories)
2. Geofabrik Taginfo India counts and OSM tag mappings
3. Multilingual and Indic aliases (Wikidata CC0)
4. Sibling-based contrastive negative extraction
5. Fast, deterministic offline indexing & lookup without runtime LLM dependencies (<1ms inverted index)
"""

from __future__ import annotations

import csv
import json
import logging
import os
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

TAXONOMY_DIR = Path(__file__).resolve().parents[2] / "data" / "taxonomy"
OVERTURE_CSV = TAXONOMY_DIR / "overture_hierarchy.csv"
TAGINFO_JSON = TAXONOMY_DIR / "india_taginfo.json"
WIKIDATA_JSON = TAXONOMY_DIR / "wikidata_aliases.json"


def normalize_text(text: str) -> str:
    """Normalize text: strip diacritics, lowercase, clean punctuation, collapse whitespace."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_str = nfkd.encode("ascii", "ignore").decode("ascii")
    clean = re.sub(r"[^\w\s-]", " ", ascii_str.lower())
    return re.sub(r"\s+", " ", clean).strip()


@dataclass
class OvertureCategory:
    group_l0: str
    level: int
    is_basic: bool
    primary_hierarchy: str
    primary_category: str
    display_name: str
    basic_category: str
    parent_path: str
    siblings: list[str] = field(default_factory=list)


class TaxonomySpine:
    """In-memory indexed taxonomy spine with fast inverted-index retrieval."""

    def __init__(self) -> None:
        self.categories: dict[str, OvertureCategory] = {}
        self.basic_categories: set[str] = set()
        self.hierarchy_to_cat: dict[str, str] = {}
        self.parent_to_children: dict[str, list[str]] = {}
        self.display_to_cat: dict[str, str] = {}
        self.token_to_cats: dict[str, set[str]] = {}
        self.taginfo_tags: dict[str, dict[str, Any]] = {}
        self.tag_aliases: dict[str, list[str]] = {}
        self.loaded = False

    def load(self) -> None:
        if self.loaded:
            return

        # 1. Load Overture Hierarchy CSV
        if OVERTURE_CSV.exists():
            with open(OVERTURE_CSV, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    cat_id = row.get("New Primary Category", "").strip()
                    if not cat_id:
                        continue
                    group_l0 = row.get("Group (L0)", "").strip()
                    level = int(row.get("Level", "0") or 0)
                    is_basic = row.get("Is Basic", "").upper() == "TRUE"
                    hierarchy = row.get("New Primary Hierarchy", "").strip()
                    display_name = row.get("New Display Name", "").strip()
                    basic_cat = row.get("New Basic Level Category", "").strip()

                    # Extract parent path
                    parts = [p.strip() for p in hierarchy.split(">")]
                    parent_path = " > ".join(parts[:-1]) if len(parts) > 1 else group_l0

                    cat_obj = OvertureCategory(
                        group_l0=group_l0,
                        level=level,
                        is_basic=is_basic,
                        primary_hierarchy=hierarchy,
                        primary_category=cat_id,
                        display_name=display_name,
                        basic_category=basic_cat or cat_id,
                        parent_path=parent_path,
                    )
                    self.categories[cat_id] = cat_obj
                    self.hierarchy_to_cat[hierarchy] = cat_id
                    disp_norm = normalize_text(display_name)
                    self.display_to_cat[disp_norm] = cat_id
                    if is_basic:
                        self.basic_categories.add(cat_id)

                    self.parent_to_children.setdefault(parent_path, []).append(cat_id)

                    # Inverted index for sub-millisecond keyword token mapping
                    for tok in set(cat_id.split("_") + disp_norm.split()):
                        if len(tok) > 2:
                            self.token_to_cats.setdefault(tok, set()).add(cat_id)

            # Assign siblings
            for cat_id, cat_obj in self.categories.items():
                children = self.parent_to_children.get(cat_obj.parent_path, [])
                cat_obj.siblings = [c for c in children if c != cat_id]

        # 2. Load Taginfo India
        if TAGINFO_JSON.exists():
            try:
                with open(TAGINFO_JSON, mode="r", encoding="utf-8") as f:
                    data = json.load(f)
                    for key, items in data.items():
                        for it in items:
                            val = it.get("value", "")
                            if val:
                                tag_str = f"{key}={val}"
                                self.taginfo_tags[tag_str] = {
                                    "key": key,
                                    "value": val,
                                    "count": it.get("count", 0),
                                    "description": it.get("description", ""),
                                }
                                val_norm = normalize_text(val.replace("_", " "))
                                self.tag_aliases.setdefault(val_norm, []).append(tag_str)
            except Exception as e:
                logger.warning(f"Error loading taginfo JSON: {e}")

        # 3. Load Wikidata Aliases
        if WIKIDATA_JSON.exists():
            try:
                with open(WIKIDATA_JSON, mode="r", encoding="utf-8") as f:
                    data = json.load(f)
                    for b in data:
                        tag = b.get("osmtag", {}).get("value", "")
                        label = b.get("label", {}).get("value", "")
                        alt = b.get("alt", {}).get("value", "")
                        for term in [label, alt]:
                            if term:
                                norm = normalize_text(term)
                                if norm and tag:
                                    self.tag_aliases.setdefault(norm, []).append(tag)
            except Exception as e:
                logger.warning(f"Error loading Wikidata aliases: {e}")

        self.loaded = True

    def get_category(self, cat_id: str) -> OvertureCategory | None:
        self.load()
        return self.categories.get(cat_id)

    def get_siblings(self, cat_id: str) -> list[str]:
        cat = self.get_category(cat_id)
        return cat.siblings if cat else []

    def find_matching_category(self, text: str) -> tuple[str | None, float]:
        """Find the best matching Overture category for an input phrase using fast inverted index."""
        self.load()
        norm = normalize_text(text)
        norm_underscore = norm.replace(" ", "_")

        # 1. Exact primary category ID
        if norm_underscore in self.categories:
            return norm_underscore, 1.0

        # 2. Exact display name
        if norm in self.display_to_cat:
            return self.display_to_cat[norm], 0.98

        # 3. Candidate search via inverted token index
        tokens = [w for w in norm.split() if len(w) > 2]
        if not tokens:
            return None, 0.0

        candidate_cats: set[str] = set()
        for tok in tokens:
            candidate_cats.update(self.token_to_cats.get(tok, set()))

        if not candidate_cats:
            return None, 0.0

        best_cat = None
        best_score = 0.0

        for cat_id in candidate_cats:
            cat = self.categories[cat_id]
            disp_norm = normalize_text(cat.display_name)
            cat_norm = cat_id.replace("_", " ")

            if norm == disp_norm or norm == cat_norm:
                score = 0.95
            elif norm in disp_norm or norm in cat_norm:
                score = 0.90
            elif all(t in disp_norm or t in cat_norm for t in tokens):
                score = 0.85
            else:
                overlap = sum(1 for t in tokens if t in disp_norm or t in cat_norm)
                score = (overlap / len(tokens)) * 0.75

            if score > best_score:
                best_score = score
                best_cat = cat_id

        if best_score >= 0.70:
            return best_cat, best_score
        return None, 0.0


_spine_instance: TaxonomySpine | None = None


def get_taxonomy_spine() -> TaxonomySpine:
    global _spine_instance
    if _spine_instance is None:
        _spine_instance = TaxonomySpine()
        _spine_instance.load()
    return _spine_instance
