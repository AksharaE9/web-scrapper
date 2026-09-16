"""
N0 — InputNormalizer

Validates and normalises the QueryInput.
If raw_text is provided, parses it into structured location + keywords.
Critical: validation errors raise 422 before run starts.
"""

from __future__ import annotations

import re
from typing import Any

from app.graph.runtime import node
from app.graph.state import LocationInput, QueryInput, RunState

# Common Indian city name aliases (Romanisation variants)
CITY_ALIASES: dict[str, str] = {
    "bangalore": "Bengaluru",
    "bengalore": "Bengaluru",
    "bombay": "Mumbai",
    "madras": "Chennai",
    "calcutta": "Kolkata",
    "mysore": "Mysuru",
    "poona": "Pune",
    "baroda": "Vadodara",
    "gauhati": "Guwahati",
    "cochi": "Kochi",
    "cochin": "Kochi",
}

# Common area misspellings (rapidfuzz handles the rest at N1)
AREA_ALIASES: dict[str, str] = {
    "kormangala": "Koramangala",
    "koramangal": "Koramangala",
    "kormangla": "Koramangala",
    "indirangar": "Indiranagar",
    "indiranagar": "Indiranagar",
    "jp nagar": "JP Nagar",
    "jpnagar": "JP Nagar",
}


def _normalise_text(text: str) -> str:
    return " ".join(text.strip().split())


def _apply_alias(text: str, alias_map: dict[str, str]) -> str:
    key = text.strip().lower()
    return alias_map.get(key, text)


def _parse_raw_text(raw: str) -> tuple[list[str], LocationInput]:
    """
    Simple heuristic parse of "gyms in Koramangala, Karnataka, India".
    Returns (keywords, LocationInput).
    LLM-assisted parse is in llm/ollama_client.py and called if LLM_ENABLED.
    """
    # Split on " in " to separate what from where
    parts = re.split(r"\s+in\s+", raw, maxsplit=1, flags=re.IGNORECASE)
    if len(parts) == 2:
        kw_part, loc_part = parts
        keywords = [k.strip() for k in re.split(r"[,;]", kw_part) if k.strip()]
        loc_parts = [p.strip() for p in loc_part.split(",")]
    else:
        # No "in": treat first token-group as keyword, rest as location
        tokens = [t.strip() for t in raw.split(",")]
        keywords = [tokens[0]] if tokens else [raw]
        loc_parts: list[str] = tokens[1:] if len(tokens) > 1 else []

    # Map loc_parts heuristically: first is locality, then city, then state, country
    locality = loc_parts[0] if len(loc_parts) > 0 else None
    city_or_state = loc_parts[1] if len(loc_parts) > 1 else None
    state = loc_parts[2] if len(loc_parts) > 2 else city_or_state
    country = loc_parts[3] if len(loc_parts) > 3 else "India"

    return keywords, LocationInput(
        raw_text=raw,
        locality=locality,
        city=city_or_state if len(loc_parts) > 2 else None,
        state=state,
        country=country,
    )


@node("n0_input", critical=True, max_retries=0)
async def run(state: RunState) -> dict[str, Any]:
    raw_q = state.get("query")
    if isinstance(raw_q, str):
        import json
        raw_q = json.loads(raw_q)
    if isinstance(raw_q, dict):
        query = QueryInput(**raw_q)
    elif isinstance(raw_q, QueryInput):
        query = raw_q
    else:
        raise ValueError(f"Invalid query input type: {type(raw_q)}")

    # Parse raw_text if provided and fields are empty
    if query.location.raw_text and not query.location.locality:
        keywords, loc = _parse_raw_text(query.location.raw_text)
        if not query.keywords:
            query = query.model_copy(update={"keywords": keywords})
        query = query.model_copy(update={"location": loc})

    # Apply city aliases
    loc = query.location
    if loc.city:
        loc = loc.model_copy(update={"city": _apply_alias(loc.city, CITY_ALIASES)})
    if loc.locality:
        loc = loc.model_copy(update={"locality": _apply_alias(loc.locality, AREA_ALIASES)})

    # Normalise whitespace
    loc = loc.model_copy(update={
        "locality": _normalise_text(loc.locality) if loc.locality else None,
        "city": _normalise_text(loc.city) if loc.city else None,
        "state": _normalise_text(loc.state) if loc.state else None,
    })

    query = query.model_copy(update={
        "location": loc,
        "keywords": [_normalise_text(k) for k in query.keywords if k.strip()],
        "exclude_keywords": [_normalise_text(k) for k in query.exclude_keywords if k.strip()],
    })

    return {"query": query}
