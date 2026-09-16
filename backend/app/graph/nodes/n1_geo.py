"""
N1 — GeoResolverAgent

Resolution priority:
  1. Area seeds (local database lookup)
  2. Nominatim (cached, max 1 req/s)
  3. Photon (fallback)
  4. Buffered point / Bounding Box (confidence >= 0.7)

COORDINATE CONVENTION: (longitude, latitude) everywhere — GeoJSON / PostGIS order.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from typing import Any

import httpx
import shapely.wkt
from langgraph.types import interrupt
from rapidfuzz import fuzz
from shapely.geometry import Point, box, shape

from app.db.pool import get_conn
from app.graph.runtime import node
from app.graph.state import GeoResolution, LocationInput, RunState
from app.settings import settings

logger = logging.getLogger(__name__)

# ── Nominatim rate limiter (global, 1 req/s across all concurrent runs) ───────
_nom_lock = asyncio.Lock()
_nom_last_call = 0.0
NOM_MIN_INTERVAL = 1.05


async def _nom_rate_limit() -> None:
    global _nom_last_call
    async with _nom_lock:
        now = time.monotonic()
        wait = NOM_MIN_INTERVAL - (now - _nom_last_call)
        if wait > 0:
            await asyncio.sleep(wait)
        _nom_last_call = time.monotonic()


# ── Place-type buffer distances (metres) ──────────────────────────────────────
BUFFER_BY_TYPE: dict[str, int] = {
    "neighbourhood": 800,
    "microhood": 500,
    "locality": 1500,
    "suburb": 1500,
    "county": 8000,
    "region": 20000,
    "city": 8000,
    "default": 1500,
}


def _buffer_m_for_type(place_type: str) -> int:
    return BUFFER_BY_TYPE.get(place_type, BUFFER_BY_TYPE["default"])


def _calc_confidence(
    name_match_score: float,
    subtype: str,
    state_match: bool,
    n_competitors: int,
) -> float:
    subtype_weights = {
        "microhood": 1.0, "neighbourhood": 0.95, "locality": 0.9,
        "suburb": 0.85, "county": 0.7, "region": 0.5,
    }
    base = (
        name_match_score * 0.4
        + subtype_weights.get(subtype, 0.6) * 0.3
        + (0.2 if state_match else 0.0)
        + max(0, 0.1 - 0.02 * n_competitors)
    )
    return min(1.0, max(0.0, base))


import math

def haversine_distance_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Calculate the great-circle distance between two points in meters."""
    R = 6371000.0  # Earth's radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


# ── Nominatim geocoder ────────────────────────────────────────────────────────

async def _nominatim_search(loc: LocationInput) -> list[dict[str, Any]]:
    """Search Nominatim with caching and progressive query variations."""
    locality = (loc.locality or "").strip()
    city = (loc.city or "").strip()
    state = (loc.state or "").strip()
    country = (loc.country or "India").strip()
    target = locality or city or loc.raw_text or ""

    queries = []
    if locality and city:
        queries.append(f"{locality}, {city}, {state}, {country}".strip(", "))
        queries.append(f"{locality}, {city}".strip(", "))
        queries.append(f"{locality}".strip(", "))
    elif locality:
        queries.append(f"{locality}, {state}, {country}".strip(", "))
        queries.append(f"{locality}".strip(", "))
    elif city:
        queries.append(f"{city}, {state}, {country}".strip(", "))
        queries.append(f"{city}".strip(", "))
    elif target:
        queries.append(target)

    # Compound name spacing variants (e.g. irramanzil -> irram manzil)
    if locality and " " not in locality and len(locality) > 5:
        for idx in [5, 4, 6]:
            if idx < len(locality):
                split_name = f"{locality[:idx]} {locality[idx:]}"
                if city:
                    queries.append(f"{split_name}, {city}")
                queries.append(split_name)

    headers = {
        "User-Agent": "LeadCoreZeroBot/2.0 (contact@leadcore.dev)",
        "Accept": "application/json",
    }

    all_results: list[dict[str, Any]] = []

    for q in queries:
        cache_key = hashlib.sha256(f"nominatim:{q}".encode()).hexdigest()
        try:
            async with get_conn() as conn:
                cached = await (await conn.execute(
                    "SELECT response FROM geo_cache WHERE query_hash = %s", (cache_key,)
                )).fetchone()
                if cached:
                    raw_resp = cached["response"]
                    cached_data = json.loads(raw_resp) if isinstance(raw_resp, str) else raw_resp
                    cached_list = cached_data.get("results", [])
                    if cached_list:
                        return list(cached_list)
        except Exception:
            pass

        await _nom_rate_limit()
        params: dict[str, Any] = {
            "q": q,
            "format": "json",
            "polygon_geojson": 1,
            "addressdetails": 1,
            "limit": 5,
        }
        if country.lower() in ("india", "in"):
            params["countrycodes"] = "in"

        try:
            async with httpx.AsyncClient(timeout=8, headers=headers) as client:
                r = await client.get(f"{settings.nominatim_url}/search", params=params)
                if r.status_code == 200:
                    results_data = r.json()
                    if isinstance(results_data, list) and results_data:
                        # Cache the response
                        try:
                            async with get_conn() as conn:
                                await conn.execute(
                                    "INSERT INTO geo_cache (query_hash, provider, response) VALUES (%s, 'nominatim', %s)",
                                    (cache_key, json.dumps({"results": results_data})),
                                )
                                await conn.commit()
                        except Exception:
                            pass
                        all_results.extend(results_data)
                        break
        except Exception as e:
            logger.debug(f"Nominatim search warning for '{q}': {e}")

    return all_results


async def _photon_search(loc: LocationInput) -> list[dict[str, Any]]:
    """Photon fallback geocoder with multiple query variations."""
    locality = (loc.locality or "").strip()
    city = (loc.city or "").strip()
    state = (loc.state or "").strip()
    country = (loc.country or "India").strip()
    target = locality or city or loc.raw_text or ""

    queries = []
    if locality and city:
        queries.append(f"{locality} {city}")
        queries.append(locality)
        queries.append(f"{locality}, {city}, {state}, {country}".strip(", "))
    elif locality:
        queries.append(locality)
    elif city:
        queries.append(city)
    elif target:
        queries.append(target)

    if locality and " " not in locality and len(locality) > 5:
        for idx in [5, 4, 6]:
            if idx < len(locality):
                queries.append(f"{locality[:idx]} {locality[idx:]}")

    try:
        headers = {"User-Agent": "LeadCoreZero/2.0"}
        async with httpx.AsyncClient(timeout=8, headers=headers) as client:
            for q in queries:
                r = await client.get(f"{settings.photon_url}/api", params={"q": q, "limit": 5})
                if r.status_code == 200:
                    data = r.json()
                    if isinstance(data, dict):
                        features = data.get("features", [])
                        if features:
                            return list(features)
    except Exception as e:
        logger.debug(f"Photon search warning: {e}")
    return []


def _buffer_for_target(locality: bool, max_results: int = 100) -> int:
    """Scale geographic buffer radius dynamically based on target lead quantity."""
    if locality:
        if max_results <= 100:
            return 2500
        elif max_results <= 300:
            return 4500
        elif max_results <= 1000:
            return 8000
        else:
            return 14000
    else:
        if max_results <= 100:
            return 6000
        elif max_results <= 300:
            return 10000
        elif max_results <= 1000:
            return 18000
        else:
            return 30000


# ── Main resolver ─────────────────────────────────────────────────────────────

async def resolve_location(loc: LocationInput, max_results: int = 100) -> GeoResolution:
    """
    Resolve a LocationInput to a GeoResolution.
    Called by N1 node and also by /api/geo/preview.
    """
    locality = (loc.locality or "").strip()
    city = (loc.city or "").strip()
    state_hint = (loc.state or "").strip()
    country = (loc.country or "India").strip()
    target = locality or city or loc.raw_text or ""

    buf_m = _buffer_for_target(bool(locality), max_results)

    # ── Step 0: Check area_seeds in database ─────────────────────────────
    try:
        async with get_conn() as conn:
            cur = await conn.execute(
                """
                SELECT locality, city, state, country, lon, lat, pincode
                FROM area_seeds
                WHERE (locality LIKE %s OR area LIKE %s)
                ORDER BY CASE WHEN city LIKE %s THEN 0 ELSE 1 END
                LIMIT 1
                """,
                (f"%{target}%", f"%{target}%", f"%{city}%")
            )
            seed_row = await cur.fetchone()
            if seed_row and seed_row.get("lon") and seed_row.get("lat"):
                lon, lat = float(seed_row["lon"]), float(seed_row["lat"])
                buf_deg = buf_m / 111_000
                geom = Point(lon, lat).buffer(buf_deg)
                bounds = geom.bounds
                return GeoResolution(
                    display_name=f"{seed_row['locality']}, {seed_row['city']}, {seed_row['state'] or ''}, {country}".strip(", "),
                    osm_id=f"seed/{seed_row['locality']}",
                    polygon_wkt=geom.wkt,
                    boundary_kind="seed_polygon",
                    buffer_m=buf_m,
                    bbox=(bounds[0], bounds[1], bounds[2], bounds[3]),
                    centroid=(lon, lat),
                    geo_confidence=0.95,
                    alternatives=[],
                )
    except Exception:
        pass

    # ── Step 1: Nominatim ────────────────────────────────────────────────
    candidates = await _nominatim_search(loc)
    best = None
    best_score = 0.0

    for item in candidates:
        addr = item.get("address", {})
        item_state = addr.get("state", "")
        disp = item.get("display_name", "")
        name_in_response = addr.get("suburb") or addr.get("neighbourhood") or addr.get("village") or addr.get("city") or disp
        
        score = fuzz.token_sort_ratio(target.lower(), name_in_response.lower()) / 100.0
        if locality:
            loc_score = fuzz.partial_ratio(locality.lower(), disp.lower()) / 100.0
            score = max(score, loc_score)

        if city and city.lower() not in disp.lower() and city.lower() not in addr.get("city", "").lower() and city.lower() not in addr.get("state_district", "").lower():
            score *= 0.6

        state_match = (
            not state_hint
            or fuzz.partial_ratio(state_hint.lower(), item_state.lower()) > 60
        )
        if not state_match:
            score *= 0.8

        if score > best_score:
            best_score = score
            best = item

    if best and ((locality and best_score >= 0.55) or (not locality and best_score >= 0.50)):
        lat = float(best["lat"])
        lon = float(best["lon"])
        geojson = best.get("geojson")

        geom = None
        boundary_kind = "admin_polygon"
        if geojson:
            try:
                geom = shape(geojson)
                if geom.geom_type == "Point":
                    geom = geom.buffer(buf_m / 111_000)
                    boundary_kind = "buffered_point"
            except Exception:
                geom = None

        if geom is None:
            geom = Point(lon, lat).buffer(buf_m / 111_000)
            boundary_kind = "buffered_point"

        centroid = geom.centroid
        bbox_bounds = geom.bounds

        return GeoResolution(
            display_name=f"{locality or best.get('display_name', '').split(',')[0]}, {city or ''}, {state_hint or ''}, {country}".strip(", "),
            osm_id=str(best.get("osm_id", "0")),
            polygon_wkt=geom.wkt,
            boundary_kind=boundary_kind,
            buffer_m=buf_m,
            bbox=(bbox_bounds[0], bbox_bounds[1], bbox_bounds[2], bbox_bounds[3]),
            centroid=(centroid.x, centroid.y),
            geo_confidence=max(0.85, best_score),
            alternatives=[
                {"display_name": c.get("display_name"), "osm_id": c.get("osm_id")}
                for c in candidates if c is not best
            ],
        )

    # ── Step 2: Photon fallback ──────────────────────────────────────────
    photon_results = await _photon_search(loc)
    for feature in photon_results:
        props = feature.get("properties", {})
        coords = feature.get("geometry", {}).get("coordinates", [])
        if not coords or len(coords) < 2:
            continue
        lon, lat = coords[0], coords[1]
        name = props.get("name", "")
        f_city = props.get("city", "")
        f_state = props.get("state", "")

        score = fuzz.token_sort_ratio(target.lower(), name.lower()) / 100.0
        if locality:
            loc_score = fuzz.partial_ratio(locality.lower(), name.lower()) / 100.0
            score = max(score, loc_score)

        if city and f_city and city.lower() not in f_city.lower() and city.lower() not in f_state.lower():
            score *= 0.7

        if (locality and score >= 0.50) or (not locality and score >= 0.40):
            buf_deg = buf_m / 111_000
            geom = Point(lon, lat).buffer(buf_deg)
            centroid = geom.centroid
            bounds = geom.bounds
            return GeoResolution(
                display_name=f"{locality or name}, {city or f_city}, {state_hint or f_state}, {country}".strip(", "),
                osm_id=str(props.get("osm_id", "photon")),
                polygon_wkt=geom.wkt,
                boundary_kind="buffered_point",
                buffer_m=buf_m,
                bbox=(bounds[0], bounds[1], bounds[2], bounds[3]),
                centroid=(lon, lat),
                geo_confidence=0.88,
                alternatives=[],
            )

    # Default fallback
    lon, lat = (78.456, 17.420) if "hyderabad" in (city.lower() + locality.lower()) else (77.624, 12.935)
    geom = Point(lon, lat).buffer(buf_m / 111_000)
    bounds = geom.bounds
    return GeoResolution(
        display_name=f"{target}, {city or 'Bengaluru'}, {state_hint or 'Karnataka'}, {country}",
        osm_id="fallback",
        polygon_wkt=geom.wkt,
        boundary_kind="fallback_point",
        buffer_m=buf_m,
        bbox=(bounds[0], bounds[1], bounds[2], bounds[3]),
        centroid=(lon, lat),
        geo_confidence=0.75,
        alternatives=[],
    )


# ── Disambiguation interrupt node ─────────────────────────────────────────────

async def disambiguation_interrupt(state: RunState) -> dict[str, Any]:
    geo = state.get("geo")
    alternatives: list[dict[str, Any]] = geo.alternatives if geo else []
    choice = interrupt({
        "type": "disambiguation",
        "message": "Multiple areas matched. Please pick one.",
        "alternatives": alternatives,
    })
    return {"disambiguation_choice": choice}


# ── LangGraph node entry point ────────────────────────────────────────────────

@node("n1_geo", critical=True, max_retries=3)
async def run(state: RunState) -> dict[str, Any]:
    loc = state["query"].location
    max_results = state["query"].max_results or 100

    choice = state.get("disambiguation_choice")
    if choice:
        geo_prev = state.get("geo")
        if geo_prev:
            for alt in geo_prev.alternatives:
                if str(alt.get("osm_id")) == choice:
                    loc = LocationInput(
                        locality=alt.get("display_name", "").split(",")[0],
                        state=loc.state,
                        country=loc.country,
                    )
                    break

    geo = await resolve_location(loc, max_results=max_results)
    return {"geo": geo}
