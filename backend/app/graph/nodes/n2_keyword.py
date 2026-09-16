"""
N2 — KeywordPlannerAgent

Resolution chain:
  1. taxonomy_rules (config/keyword_rules.yaml) — highest precision
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

import yaml

from app.db.pool import get_conn
from app.graph.runtime import node
from app.graph.state import KeywordPlan, RunState
from app.settings import settings

logger = logging.getLogger(__name__)

# ── Taxonomy rules ────────────────────────────────────────────────────────────

_RULES_PATH = Path(__file__).resolve().parents[3] / "config" / "keyword_rules.yaml"
_rules: dict[str, Any] | None = None

GENERIC_RETAIL_STOPWORDS = {
    "store", "stores", "shop", "shops", "mart", "marts", "center", "centers",
    "centre", "centres", "service", "services", "care", "club", "clubs", "hub",
    "place", "zone", "point", "junction", "enterprise", "enterprises", "trader",
    "traders", "agency", "agencies", "co", "company"
}


def _load_rules() -> dict[str, Any]:
    global _rules
    if _rules is None:
        if _RULES_PATH.exists():
            with open(_RULES_PATH, encoding="utf-8") as f:
                _rules = yaml.safe_load(f) or {}
        else:
            _rules = {}
    return _rules


def _normalise_keyword(kw: str) -> str:
    """Lowercase, strip diacritics, collapse whitespace."""
    nfkd = unicodedata.normalize("NFKD", kw)
    ascii_ = nfkd.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", ascii_.lower().strip())


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
            logger.info(f"Fastembed embedding model disabled: {e}")
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


def _build_plan_from_rule(keyword: str, rule: dict[str, Any]) -> KeywordPlan:
    """Build a KeywordPlan from a keyword_rules.yaml entry."""
    return KeywordPlan(
        keyword=keyword,
        synonyms=rule.get("synonyms", []),
        overture_basic_categories=rule.get("overture_basic_categories", []),
        overture_taxonomy_paths=rule.get("overture_taxonomy_paths", []),
        osm_tag_filters=rule.get("osm", []),
        name_patterns=rule.get("name_patterns", []),
        exclude_patterns=rule.get("exclude_patterns", []),
        plan_confidence=0.9,
        planner="taxonomy_rules",
    )


def _build_plan_from_rag(keyword: str, rag_results: list[dict[str, Any]]) -> KeywordPlan:
    """Build a KeywordPlan from RAG results (no rules match)."""
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


def _minimum_plan(keyword: str) -> KeywordPlan:
    """Last resort: name-pattern only plan. Still functional."""
    safe = re.escape(keyword.lower())
    words = [re.escape(w) for w in keyword.lower().split() if len(w) > 2 and w not in GENERIC_RETAIL_STOPWORDS]
    patterns = [f"\\b{safe}\\b"] + [f"\\b{w}\\b" for w in words]

    # Generate heuristic OSM tag filters
    osm_tags: list[str] = []
    kw_lower = keyword.lower()
    if any(w in kw_lower for w in ["store", "shop", "mart", "retail"]):
        osm_tags.append("shop")
    if any(w in kw_lower for w in ["restaurant", "dining", "eatery", "food", "dine", "kitchen", "biryani"]):
        osm_tags.append("amenity=restaurant")
    if any(w in kw_lower for w in ["cafe", "coffee", "tea", "bistro", "chai"]):
        osm_tags.append("amenity=cafe")
    if any(w in kw_lower for w in ["gym", "fitness", "crossfit", "workout"]):
        osm_tags.append("leisure=fitness_centre")
        osm_tags.append("amenity=gym")
    if any(w in kw_lower for w in ["hotel", "resort", "lodging", "stay", "guest house", "hostel"]):
        osm_tags.append("tourism=hotel")
    if any(w in kw_lower for w in ["hospital", "clinic", "doctor", "nursing home"]):
        osm_tags.append("amenity=hospital")
        osm_tags.append("amenity=clinic")
    if any(w in kw_lower for w in ["pharmacy", "chemist", "medical", "druggist"]):
        osm_tags.append("amenity=pharmacy")
        osm_tags.append("shop=chemist")
    if any(w in kw_lower for w in ["electric", "electronics", "appliances", "gadgets", "mobile"]):
        osm_tags.append("shop=electronics")
        osm_tags.append("shop=electrical")

    return KeywordPlan(
        keyword=keyword,
        synonyms=[],
        overture_basic_categories=[keyword.lower()],
        overture_taxonomy_paths=[],
        osm_tag_filters=osm_tags if osm_tags else ["shop", "amenity"],
        name_patterns=list(dict.fromkeys(patterns)),
        exclude_patterns=[],
        plan_confidence=0.6,
        planner="taxonomy_rules",
    )


async def plan_keyword(keyword: str, llm_enabled: bool = False) -> KeywordPlan:
    """
    Plan a single keyword. Tries:
      1. keyword_plans cache (previous successful plan)
      2. taxonomy_rules (exact rule key, synonym match, or significant word overlap)
      3. RAG (pgvector similarity search)
      4. LLM refinement (if enabled)
      5. Minimum name-pattern plan
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

    # 2. Try taxonomy rules
    rules = _load_rules()
    if rules:
        # Phase 2a: Exact rule key or synonym match
        for rule_key, rule in rules.items():
            rk_norm = _normalise_keyword(rule_key.replace("_", " "))
            synonyms_norm = [_normalise_keyword(s) for s in rule.get("synonyms", [])]
            if kw_norm == rk_norm or kw_norm in synonyms_norm:
                plan = _build_plan_from_rule(keyword, rule)
                await _save_plan(kw_norm, plan)
                return plan

        # Phase 2b: Multi-word phrase or significant non-generic word overlap
        kw_sig_words = {w for w in kw_norm.split() if w not in GENERIC_RETAIL_STOPWORDS and len(w) > 2}
        for rule_key, rule in rules.items():
            rk_norm = _normalise_keyword(rule_key.replace("_", " "))
            synonyms_norm = [_normalise_keyword(s) for s in rule.get("synonyms", [])]

            if rk_norm in kw_norm or any(s in kw_norm for s in synonyms_norm):
                plan = _build_plan_from_rule(keyword, rule)
                await _save_plan(kw_norm, plan)
                return plan

            rk_sig_words = {w for w in rk_norm.split() if w not in GENERIC_RETAIL_STOPWORDS and len(w) > 2}
            for syn in synonyms_norm:
                rk_sig_words.update(w for w in syn.split() if w not in GENERIC_RETAIL_STOPWORDS and len(w) > 2)

            if kw_sig_words and rk_sig_words and (kw_sig_words & rk_sig_words):
                plan = _build_plan_from_rule(keyword, rule)
                await _save_plan(kw_norm, plan)
                return plan

    # 3. Try RAG
    rag_results = await _rag_lookup(kw_norm)
    if rag_results:
        plan = _build_plan_from_rag(keyword, rag_results)

        # Optional LLM refinement
        if llm_enabled and settings.llm_enabled:
            try:
                from app.llm.ollama_client import refine_keyword_plan
                plan = await refine_keyword_plan(keyword, plan, rag_results)
                plan = plan.model_copy(update={"planner": "rag+llm"})
            except Exception:
                pass

        await _save_plan(kw_norm, plan)
        return plan

    # 4. Minimum fallback
    plan = _minimum_plan(keyword)
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
        # Always ensure name_patterns is non-empty
        if not plan.name_patterns:
            safe = re.escape(kw.lower())
            plan = plan.model_copy(update={"name_patterns": [f"\\b{safe}\\b"]})
        plans.append(plan)

    return {"plans": plans}
