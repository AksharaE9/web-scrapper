"""
N2 — KeywordPlannerAgent

Unified resolution chain:
  1. Concept Cards & Taxonomy (resolve_concept) — authoritative, unified SMB & Overture taxonomy
  2. RAG over taxonomy_vectors (pgvector cosine similarity)
  3. Optional LLM refinement (JSON schema, only from retrieved list)

Saves successful plans to keyword_plans for query memory (future reuse).
Name patterns are MANDATORY even when category/tag matching is available
— OSM tagging in Indian cities is sparse.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from pathlib import Path
from typing import Any

from app.db.pool import get_conn
from app.graph.runtime import node
from app.graph.state import KeywordPlan, RunState
from app.llm.ollama_client import refine_keyword_plan
from app.relevance.concepts import resolve_concept, load_all_cards, ConceptCard
from app.settings import settings

logger = logging.getLogger(__name__)

GENERIC_RETAIL_STOPWORDS = {
    "store", "stores", "shop", "shops", "mart", "marts", "center", "centers",
    "centre", "centres", "service", "services", "care", "club", "clubs", "hub",
    "place", "zone", "point", "junction", "enterprise", "enterprises", "trader",
    "traders", "agency", "agencies", "co", "company"
}


def _normalise_keyword(kw: str) -> str:
    """Lowercase, strip diacritics, collapse whitespace."""
    nfkd = unicodedata.normalize("NFKD", kw)
    ascii_ = nfkd.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", ascii_.lower().strip())


def _load_rules() -> dict[str, Any]:
    """Compatibility dictionary loaded directly from unified Concept Cards."""
    cards = load_all_cards()
    rules: dict[str, Any] = {}
    for cid, card in cards.items():
        rules[cid] = {
            "synonyms": card.labels,
            "overture_basic_categories": card.overture_basic_categories or [cid],
            "overture_taxonomy_paths": card.overture_taxonomy_paths,
            "osm": card.osm_tags or [f"shop={cid}"],
            "name_patterns": card.name_patterns or [f"\\b{re.escape(cid.replace('_', ' '))}\\b"],
            "exclude_patterns": card.veto_terms,
        }
    return rules


def _build_plan_from_card(keyword: str, card: ConceptCard) -> KeywordPlan:
    """Build a KeywordPlan from a resolved ConceptCard."""
    safe_kw = re.escape(keyword.lower())
    name_patterns = card.name_patterns or [f"\\b{safe_kw}\\b"]
    if f"\\b{safe_kw}\\b" not in name_patterns:
        name_patterns = [f"\\b{safe_kw}\\b"] + name_patterns

    osm_filters = list(card.osm_tags) if card.osm_tags else []
    for cat in card.categories.defining:
        if "=" in cat:
            osm_filters.append(cat)
        elif not any(cat in tag for tag in osm_filters):
            osm_filters.append(f"shop={cat}")

    return KeywordPlan(
        keyword=keyword,
        synonyms=card.labels,
        overture_basic_categories=card.overture_basic_categories or [card.concept_id],
        overture_taxonomy_paths=card.overture_taxonomy_paths,
        osm_tag_filters=list(dict.fromkeys(osm_filters)),
        name_patterns=list(dict.fromkeys(name_patterns)),
        exclude_patterns=card.veto_terms,
        plan_confidence=max(0.80, card.confidence),
        planner="taxonomy_rules",
    )


def _build_plan_from_rule(keyword: str, rule: dict[str, Any]) -> KeywordPlan:
    """Build a KeywordPlan from a rule dictionary."""
    return KeywordPlan(
        keyword=keyword,
        synonyms=rule.get("synonyms", []),
        overture_basic_categories=rule.get("overture_basic_categories", []),
        overture_taxonomy_paths=rule.get("overture_taxonomy_paths", []),
        osm_tag_filters=rule.get("osm", []),
        name_patterns=rule.get("name_patterns", [f"\\b{re.escape(keyword.lower())}\\b"]),
        exclude_patterns=rule.get("exclude_patterns", []),
        plan_confidence=0.9,
        planner="taxonomy_rules",
    )


# ── Embedding model (lazy loaded, shared across calls) ────────────────────────
_embed_model: Any = None
_embed_model_failed: bool = False


def _get_embed_model() -> Any:
    global _embed_model, _embed_model_failed
    if _embed_model_failed:
        return None
    if _embed_model is None:
        try:
            from fastembed import TextEmbedding
            _embed_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
        except Exception as e:
            logger.warning(f"Fastembed embedding model failed to initialize: {e}")
            _embed_model_failed = True
            return None
    return _embed_model


async def _rag_lookup(keyword_norm: str, top_k: int = 8) -> list[dict[str, Any]]:
    """Vector similarity search over taxonomy_vectors."""
    model = _get_embed_model()
    if not model:
        return []

    try:
        embedding = list(model.embed([f"query: {keyword_norm}"]))[0].tolist()
        async with get_conn() as conn:
            rows = await (await conn.execute(
                f"""
                SELECT id, system, label, path,
                       1 - (embedding <=> %s::vector) AS similarity
                FROM taxonomy_vectors
                WHERE 1 - (embedding <=> %s::vector) >= 0.55
                ORDER BY similarity DESC
                LIMIT %s
                """,
                (embedding, embedding, top_k),
            )).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def _build_plan_from_rag(keyword: str, rag_results: list[dict[str, Any]]) -> KeywordPlan:
    """Build a KeywordPlan from RAG results."""
    overture_cats = [r["id"] for r in rag_results if r.get("system") == "overture"]
    osm_tags = [r["id"] for r in rag_results if r.get("system") == "osm"]

    safe = re.escape(keyword.lower())
    name_patterns = [f"\\b{safe}\\b"]

    synonyms = list({r["label"] for r in rag_results if r.get("similarity", 0) >= 0.7})
    confidence = sum(r.get("similarity", 0.5) for r in rag_results) / max(len(rag_results), 1)

    return KeywordPlan(
        keyword=keyword,
        synonyms=synonyms,
        overture_basic_categories=overture_cats,
        overture_taxonomy_paths=[],
        osm_tag_filters=osm_tags,
        name_patterns=name_patterns,
        exclude_patterns=[],
        plan_confidence=min(0.85, confidence),
        planner="rag",
    )


async def plan_keyword(keyword: str, llm_enabled: bool = False) -> KeywordPlan:
    """
    Plan a single keyword using unified Concept Card resolution:
      1. keyword_plans cache (previous successful plan)
      2. Unified Concept Card resolution (seeded, alias, fuzzy, derived)
      3. RAG / Vector search fallback
      4. Optional LLM refinement (if enabled)
    """
    kw_norm = _normalise_keyword(keyword)

    # 1. Check cached plan
    try:
        async with get_conn() as conn:
            cached = await (await conn.execute(
                "SELECT plan FROM keyword_plans WHERE keyword_norm = %s", (kw_norm,)
            )).fetchone()
        if cached:
            await _increment_uses(kw_norm)
            plan_data = json.loads(cached["plan"]) if isinstance(cached["plan"], str) else cached["plan"]
            return KeywordPlan(**plan_data)
    except Exception:
        pass

    # 2. Unified Concept Card resolution
    card = resolve_concept(keyword)
    if card.provenance in ("seeded", "alias", "fuzzy", "derived", "retrieved"):
        plan = _build_plan_from_card(keyword, card)
        await _save_plan(kw_norm, plan)
        return plan

    # 3. Try RAG
    rag_results = await _rag_lookup(kw_norm)
    if rag_results:
        plan = _build_plan_from_rag(keyword, rag_results)
        if llm_enabled and settings.llm_enabled:
            try:
                plan = await refine_keyword_plan(keyword, plan, rag_results)
                plan = plan.model_copy(update={"planner": "rag+llm"})
            except Exception:
                pass
        await _save_plan(kw_norm, plan)
        return plan

    # 4. Fallback to unresolved card plan
    plan = _build_plan_from_card(keyword, card)
    await _save_plan(kw_norm, plan)
    return plan


async def _save_plan(kw_norm: str, plan: KeywordPlan) -> None:
    """Persist plan to keyword_plans for future reuse."""
    try:
        model = _get_embed_model()
        embedding = list(model.embed([f"passage: {kw_norm}"]))[0].tolist() if model else None
        async with get_conn() as conn:
            await conn.execute(
                """
                INSERT INTO keyword_plans (keyword_norm, plan, embedding, uses, updated_at)
                VALUES (%s, %s::jsonb, %s::vector, 1, NOW())
                ON CONFLICT (keyword_norm) DO UPDATE
                  SET plan = EXCLUDED.plan, embedding = EXCLUDED.embedding,
                      uses = keyword_plans.uses + 1, updated_at = NOW()
                """,
                (kw_norm, plan.model_dump_json(), json.dumps(embedding) if embedding else None),
            )
            await conn.commit()
    except Exception:
        pass


async def _increment_uses(kw_norm: str) -> None:
    try:
        async with get_conn() as conn:
            await conn.execute(
                "UPDATE keyword_plans SET uses = uses + 1 WHERE keyword_norm = %s", (kw_norm,)
            )
            await conn.commit()
    except Exception:
        pass


@node("n2_keyword", critical=True, max_retries=2)
async def run(state: RunState) -> dict[str, Any]:
    query = state["query"]
    llm_enabled = settings.llm_enabled

    plans = []
    for kw in query.keywords:
        plan = await plan_keyword(kw, llm_enabled=llm_enabled)
        if not plan.name_patterns:
            safe = re.escape(kw.lower())
            plan = plan.model_copy(update={"name_patterns": [f"\\b{safe}\\b"]})
        plans.append(plan)

    return {"plans": plans}
