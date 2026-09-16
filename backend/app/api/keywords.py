"""Keywords API — preview keyword plan."""
from __future__ import annotations
from typing import Any
from fastapi import APIRouter, Query
from app.graph.nodes.n2_keyword import plan_keyword

router = APIRouter(tags=["keywords"])


@router.get("/keywords/preview")
async def get_keyword_preview(keyword: str = Query(...)) -> dict[str, Any]:
    """Preview a keyword plan via GET query param (called by frontend)."""
    plan = await plan_keyword(keyword, llm_enabled=False)
    return plan.model_dump()


@router.post("/keywords/plan")
@router.post("/keywords/preview")
async def preview_keyword_plan(body: dict[str, Any]) -> dict[str, Any]:
    """Preview the keyword plan for one or more keywords before running."""
    if "keyword" in body and "keywords" not in body:
        plan = await plan_keyword(body["keyword"], llm_enabled=False)
        return plan.model_dump()
    keywords: list[str] = body.get("keywords", [])
    plans = []
    for kw in keywords:
        plan = await plan_keyword(kw, llm_enabled=False)
        plans.append(plan.model_dump())
    return {"plans": plans}
