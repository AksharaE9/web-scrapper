"""
Concept Cards API — LeadCore Zero v2.1
Endpoints for inspecting, resolving, and updating versioned Concept Cards.
"""

from __future__ import annotations

import json
from typing import Any
from fastapi import APIRouter, HTTPException, Path as PathParam
import yaml

from app.db.pool import get_conn
from app.relevance.concepts import (
    ConceptCard,
    CONCEPTS_DIR,
    load_card_from_disk,
    load_all_cards,
    resolve_concept,
    _DISK_CARDS_CACHE,
    _ALIAS_INDEX,
)

router = APIRouter(tags=["concepts"])


@router.get("/concepts")
async def list_concepts(q: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    """List or search available Concept Cards."""
    cards_map = load_all_cards()
    cards: list[dict[str, Any]] = []
    for cid, card in cards_map.items():
        if q:
            q_lower = q.lower()
            matches = (
                q_lower in card.concept_id.lower()
                or any(q_lower in l.lower() for l in card.labels)
                or q_lower in card.definition.lower()
            )
            if not matches:
                continue
        cards.append(card.model_dump())
        if len(cards) >= limit:
            break
    return cards


@router.get("/concepts/{keyword}")
async def get_concept_card(keyword: str = PathParam(...)) -> dict[str, Any]:
    """Retrieve the resolved ConceptCard for a keyword."""
    card = resolve_concept(keyword)
    return card.model_dump()


@router.put("/concepts/{concept_id}")
async def update_concept_card(concept_id: str, card_data: dict[str, Any]) -> dict[str, Any]:
    """Update a ConceptCard and bump its version."""
    existing = load_card_from_disk(concept_id)
    new_version = (existing.version + 1) if existing else (card_data.get("version", 1) + 1)

    card_data["concept_id"] = concept_id
    card_data["version"] = new_version

    try:
        updated_card = ConceptCard(**card_data)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid ConceptCard structure: {e}")

    # Write to disk
    CONCEPTS_DIR.mkdir(parents=True, exist_ok=True)
    yaml_path = CONCEPTS_DIR / f"{concept_id}.yaml"
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(updated_card.model_dump(), f, sort_keys=False)

    # Invalidate in-memory cache
    _DISK_CARDS_CACHE.clear()
    _ALIAS_INDEX.clear()
    load_all_cards()

    # Persist to keyword_concepts DB table
    try:
        async with get_conn() as conn:
            await conn.execute(
                """
                INSERT INTO keyword_concepts (concept_id, version, keyword_norm, card, origin)
                VALUES (%s, %s, %s, %s, 'user_edit')
                ON CONFLICT (concept_id, version) DO UPDATE SET
                    card = EXCLUDED.card
                """,
                (concept_id, new_version, concept_id, json.dumps(updated_card.model_dump())),
            )
            await conn.commit()
    except Exception:
        pass

    return updated_card.model_dump()
