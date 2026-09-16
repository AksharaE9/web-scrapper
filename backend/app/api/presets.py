"""Presets API — list, import keyword presets."""
from __future__ import annotations
import json
from typing import Any
from pathlib import Path
from fastapi import APIRouter, UploadFile, File
from app.db.pool import get_conn

router = APIRouter(tags=["presets"])

SEEDS_FILE = Path(__file__).parent.parent.parent / "seeds" / "keyword_presets.json"


@router.get("/presets")
async def list_presets() -> list[dict[str, Any]]:
    try:
        async with get_conn() as conn:
            rows = await (await conn.execute("SELECT * FROM keyword_presets ORDER BY name")).fetchall()
        if rows:
            return [dict(r) for r in rows]
    except Exception:
        pass

    # Fallback to local keyword_presets.json if DB is not yet populated or unavailable
    if SEEDS_FILE.exists():
        try:
            with open(SEEDS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return [dict(item) if isinstance(item, dict) else {"name": str(item)} for item in data]
        except Exception:
            pass
    return []


@router.post("/presets/import")
async def import_preset(file: UploadFile = File(...)) -> dict[str, Any]:
    """Import a keyword preset JSON file (KishoreRaman04 format)."""
    content = await file.read()
    data = json.loads(content)
    name = file.filename or "imported"
    categories: list[str] = data.get("search_categories", [])
    excludes: list[str] = data.get("exclude_keywords", [])
    async with get_conn() as conn:
        await conn.execute(
            """
            INSERT INTO keyword_presets (name, search_categories, exclude_keywords)
            VALUES (%s, %s, %s)
            ON CONFLICT (name) DO UPDATE
              SET search_categories = EXCLUDED.search_categories,
                  exclude_keywords = EXCLUDED.exclude_keywords
            """,
            (name, categories, excludes),
        )
        await conn.commit()
    return {"name": name, "categories": len(categories), "excludes": len(excludes)}
