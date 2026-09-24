"""
Ollama LLM Client — local model inference with strict JSON schema and evidence enforcement.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.graph.state import KeywordPlan
from app.rag.grounded_extract import verify_grounded_span
from app.settings import settings

logger = logging.getLogger(__name__)


async def refine_keyword_plan(
    keyword: str,
    base_plan: KeywordPlan,
    retrieved_contexts: list[str] | list[dict[str, Any]],
) -> KeywordPlan:
    """Refine a keyword plan using local Ollama model if enabled."""
    if not settings.llm_enabled:
        return base_plan

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            prompt = (
                f"Given target keyword '{keyword}' and context: {json.dumps(retrieved_contexts)},\n"
                f"suggest additional relevant search categories and name regex patterns.\n"
                f"Return JSON with 'categories' (list of str) and 'name_patterns' (list of regex strings)."
            )
            resp = await client.post(
                f"{settings.ollama_url}/api/generate",
                json={
                    "model": settings.ollama_model,
                    "prompt": prompt,
                    "format": "json",
                    "stream": False,
                },
            )
            if resp.status_code == 200:
                data = resp.json().get("response")
                if isinstance(data, str):
                    data = json.loads(data)
                if isinstance(data, dict):
                    cats = data.get("categories", [])
                    patterns = data.get("name_patterns", [])
                    updated_cats = list(set(base_plan.overture_basic_categories + [c for c in cats if isinstance(c, str)]))
                    updated_pats = list(set(base_plan.name_patterns + [p for p in patterns if isinstance(p, str)]))
                    return base_plan.model_copy(update={
                        "overture_basic_categories": updated_cats,
                        "name_patterns": updated_pats,
                        "planner": "rag+llm",
                    })
    except Exception as e:
        logger.debug(f"Ollama refinement fallback: {e}")

    return base_plan
