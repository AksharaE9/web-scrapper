"""
R2 — Feature Extraction for Relevance Evidence Scoring

Extracts normalized feature vector (all values in [0, 1] or {-1, 1}) from
candidate tokens, ConceptCard, metadata, semantic similarities, and web enrichments.

Category-first hierarchy (Phase 2):
  PRIMARY signals  — sufficient alone to accept (if no veto fires):
    f_def_cat   : Overture/place category in card.categories.defining
    f_def_osm   : OSM tag in card.categories.defining
    f_def_web   : defining term found in scraped web tokens
  SUPPORTING signals — never sufficient alone:
    f_def_name  : defining term in business name  ← DEMOTED in v2.2
  PENALTY:
    f_name_only_primary : 1.0 when name is the ONLY primary signal (no cat/osm/web)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from app.relevance.concepts import ConceptCard
from app.relevance.tokenize import TokenizedProfile, sanitize_raw_text


@dataclass
class RelevanceFeatures:
    f_def_name: float = 0.0
    f_def_cat: float = 0.0
    f_def_osm: float = 0.0
    f_def_web: float = 0.0
    f_sup_count: float = 0.0
    f_host_cat: float = 0.0
    f_nonev_only: float = 0.0
    f_cat_conf: float = 0.5
    f_src_agree: float = 0.0
    f_sem_pos: float = 0.0
    f_sem_neg: float = 0.0
    f_sem_margin: float = 0.0
    f_ce: float = 0.5
    # Phase 2: penalty feature — set to 1.0 when name token is the only
    # primary-tier signal (no category, no OSM tag, no web evidence).
    # Prevents "Pooja Stationers" from being accepted solely on the name token "pooja".
    f_name_only_primary: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


def extract_features(
    profile: TokenizedProfile,
    card: ConceptCard,
    raw_categories: list[str] | None = None,
    osm_tags: list[str] | None = None,
    source_confidence: float | None = None,
    source_lineage: list[str] | None = None,
    sem_pos: float = 0.0,
    sem_neg: float = 0.0,
    ce_score: float = 0.5,
) -> RelevanceFeatures:
    """Compute all R2 relevance features."""
    defining_terms = card.get_strong_defining_terms()
    supporting_terms = card.get_supporting_terms()

    # 1. f_def_name: defining term in name (SUPPORTING only — see f_name_only_primary)
    f_def_name = 0.0
    for dt in defining_terms:
        if dt in profile.evidence_tokens or dt in profile.clean_name:
            f_def_name = 1.0
            break
        for bg in profile.name_bigrams:
            if dt in bg:
                f_def_name = 1.0
                break

    # 2. f_def_cat: primary/alternate category in defining (PRIMARY)
    f_def_cat = 0.0
    defining_cats = {sanitize_raw_text(c) for c in card.categories.defining}
    if raw_categories:
        for cat in raw_categories:
            c_clean = sanitize_raw_text(cat)
            if any(dc in c_clean for dc in defining_cats):
                f_def_cat = 1.0
                break

    # 3. f_def_osm: OSM tag in defining (PRIMARY)
    f_def_osm = 0.0
    if osm_tags:
        for tag in osm_tags:
            t_clean = sanitize_raw_text(tag)
            if any(dc in t_clean for dc in defining_cats):
                f_def_osm = 1.0
                break

    # 4. f_def_web: defining term in web tokens (PRIMARY)
    f_def_web = 0.0
    for dt in defining_terms:
        if dt in profile.web_tokens:
            f_def_web = 1.0
            break

    # 5. f_sup_count: count of supporting terms
    sup_hits = 0
    for st in supporting_terms:
        if st in profile.evidence_tokens or st in profile.category_tokens or st in profile.web_tokens:
            sup_hits += 1
    f_sup_count = min(float(sup_hits) / 3.0, 1.0)

    # 6. f_host_cat: category in host list
    f_host_cat = 0.0
    host_cats = {sanitize_raw_text(c) for c in card.categories.host}
    if raw_categories:
        for cat in raw_categories:
            c_clean = sanitize_raw_text(cat)
            if any(hc in c_clean for hc in host_cats):
                f_host_cat = 1.0
                break

    # 7. f_nonev_only: name contains only non-evidence tokens + shop words
    f_nonev_only = 0.0
    meaningful_evidence = [t for t in profile.evidence_tokens if t != "<shop_word>"]
    if len(profile.non_evidence_tokens) > 0 and len(meaningful_evidence) == 0:
        f_nonev_only = 1.0

    # 8. f_cat_conf: source confidence
    f_cat_conf = float(source_confidence) if source_confidence is not None else 0.5

    # 9. f_src_agree: multiple sources agree
    f_src_agree = 0.0
    if source_lineage and len(source_lineage) > 1:
        f_src_agree = min(len(source_lineage) / 3.0, 1.0)

    # 10. Semantic margin
    f_sem_margin = sem_pos - sem_neg

    # 11. f_name_only_primary: penalty when name token is the sole primary signal.
    # A business named "Pooja Stationers" has f_def_name=1 but f_def_cat=0,
    # f_def_osm=0, f_def_web=0. This should be review-band, not accepted.
    # The scorer applies a strong negative weight to this feature.
    f_name_only_primary = 0.0
    if f_def_name == 1.0 and f_def_cat == 0.0 and f_def_osm == 0.0 and f_def_web == 0.0:
        f_name_only_primary = 1.0

    return RelevanceFeatures(
        f_def_name=f_def_name,
        f_def_cat=f_def_cat,
        f_def_osm=f_def_osm,
        f_def_web=f_def_web,
        f_sup_count=f_sup_count,
        f_host_cat=f_host_cat,
        f_nonev_only=f_nonev_only,
        f_cat_conf=f_cat_conf,
        f_src_agree=f_src_agree,
        f_sem_pos=sem_pos,
        f_sem_neg=sem_neg,
        f_sem_margin=f_sem_margin,
        f_ce=ce_score,
        f_name_only_primary=f_name_only_primary,
    )
