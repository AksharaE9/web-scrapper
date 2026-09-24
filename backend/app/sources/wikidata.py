"""
app/sources/wikidata.py — Wikidata SPARQL client for brand industry classification.
app/sources/alltheplaces.py — AllThePlaces scraper datasets.
app/sources/imports.py — User-imported CSV/JSON lead dataset parser.
"""

from __future__ import annotations

import csv
import io
import json
import logging
from pathlib import Path
from typing import Any
import httpx
from app.settings import settings

logger = logging.getLogger(__name__)


async def query_wikidata_brand_industry(brand_name: str) -> list[str]:
    """Query Wikidata SPARQL endpoint to determine brand industries (pen manufacturer, footwear, etc.)."""
    query = f"""
    SELECT ?item ?itemLabel ?industryLabel WHERE {{
      ?item ?label "{brand_name}"@en.
      OPTIONAL {{ ?item wdt:P452 ?industry. }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }} LIMIT 5
    """
    url = "https://query.wikidata.org/sparql"
    headers = {"User-Agent": settings.crawler_user_agent, "Accept": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=8.0, headers=headers) as client:
            resp = await client.get(url, params={"query": query, "format": "json"})
            if resp.status_code == 200:
                data = resp.json()
                results = []
                for b in data.get("results", {}).get("bindings", []):
                    ind = b.get("industryLabel", {}).get("value")
                    if ind:
                        results.append(ind.lower())
                return results
    except Exception as e:
        logger.warning(f"Wikidata query failed for brand '{brand_name}': {e}")
    return []


def parse_user_import_file(file_path: Path) -> list[dict[str, Any]]:
    """Parse custom user CSV or JSON lead imports into normalized candidate records."""
    if not file_path.exists():
        return []

    records: list[dict[str, Any]] = []
    if file_path.suffix.lower() == ".json":
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                records = data
        except Exception as e:
            logger.warning(f"Failed to parse import JSON {file_path}: {e}")
    elif file_path.suffix.lower() == ".csv":
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.DictReader(f)
                records = [row for row in reader]
        except Exception as e:
            logger.warning(f"Failed to parse import CSV {file_path}: {e}")
    return records
