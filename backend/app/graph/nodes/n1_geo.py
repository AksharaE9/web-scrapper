"""
N1 - GeoResolverAgent

Resolution priority (7-Tier Resolution Ladder):
  Tier 0: In-memory LRU cache (< 1ms, 15m TTL)
  Tier 1: Postgres geo_cache table keyed on normalized input (~20ms)
  Tier 2: Offline area_seeds exact + RapidFuzz typo correction (< 5ms, 0 network calls)
  Tier 3: Overture divisions parquet boundary polygon (local DuckDB)
  Tier 4: Nominatim structured query (polygon_geojson=1, max 2 requests ever)
  Tier 5: Photon geocoder fallback (Point)
  Tier 6: Buffered point with true cosine-latitude ground-width scaling

COORDINATE CONVENTION: (longitude, latitude) everywhere - GeoJSON / PostGIS order.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import time
import unicodedata
from pathlib import Path
from typing import Any

import duckdb
import httpx
import shapely.wkt
import yaml
from langgraph.types import interrupt
from rapidfuzz import fuzz
from shapely.geometry import Point, Polygon, box, mapping, shape

from app.db.pool import get_conn
from app.graph.runtime import node
from app.graph.state import BoundarySource, GeoResolution, LocationInput, RunState
from app.resolve.geo_math import haversine_distance_m
from app.settings import settings

logger = logging.getLogger(__name__)

# Dynamic Geo Configuration Loader
CONFIG_PATH = Path(__file__).resolve().parent.parent.parent.parent / "config" / "geo.yaml"
ALIASES_PATH = Path(__file__).resolve().parent.parent.parent.parent / "config" / "geo_aliases.yaml"
_CACHED_CONFIG: dict[str, Any] = {}
_CONFIG_LOAD_TIME: float = 0.0
_CACHED_ALIASES: dict[str, Any] = {}
_ALIASES_LOAD_TIME: float = 0.0


def get_geo_aliases() -> dict[str, Any]:
    global _CACHED_ALIASES, _ALIASES_LOAD_TIME
    now = time.monotonic()
    if _CACHED_ALIASES and (now - _ALIASES_LOAD_TIME < 60.0):
        return _CACHED_ALIASES

    if ALIASES_PATH.exists():
        try:
            data = yaml.safe_load(ALIASES_PATH.read_text(encoding="utf-8")) or {}
            _CACHED_ALIASES = data.get("aliases", {})
            _ALIASES_LOAD_TIME = now
            return _CACHED_ALIASES
        except Exception as e:
            logger.warning(f"Failed to read geo_aliases.yaml: {e}")

    return {}


def get_geo_config() -> dict[str, Any]:
    global _CACHED_CONFIG, _CONFIG_LOAD_TIME
    now = time.monotonic()
    if _CACHED_CONFIG and (now - _CONFIG_LOAD_TIME < 60.0):
        return _CACHED_CONFIG

    if CONFIG_PATH.exists():
        try:
            _CACHED_CONFIG = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
            _CONFIG_LOAD_TIME = now
            return _CACHED_CONFIG
        except Exception as e:
            logger.warning(f"Failed to read geo.yaml: {e}")

    # Fallback configuration if file is missing
    return {
        "nominatim": {"min_interval_s": 1.05, "timeout_s": 8.0, "max_structured_results": 8, "max_retries": 1},
        "photon": {"timeout_s": 8.0, "max_results": 5},
        "buffers_m": {"microhood": 500, "neighbourhood": 800, "locality": 1500, "suburb": 1500, "county": 8000, "city": 8000, "region": 20000, "default": 1500},
        "buffer_by_result_target": {
            "locality": [{"max_results": 100, "buffer_m": 2500}, {"max_results": 300, "buffer_m": 4500}, {"max_results": 1000, "buffer_m": 8000}, {"max_results": 5000, "buffer_m": 14000}],
            "city": [{"max_results": 100, "buffer_m": 6000}, {"max_results": 300, "buffer_m": 10000}, {"max_results": 1000, "buffer_m": 18000}, {"max_results": 5000, "buffer_m": 30000}],
        },
        "subtype_weights": {"microhood": 1.0, "neighbourhood": 0.95, "locality": 0.90, "suburb": 0.85, "county": 0.70, "region": 0.50},
        "accept_threshold": {"with_locality": 0.55, "without_locality": 0.50},
        "penalties": {"city_mismatch": 0.60, "state_mismatch": 0.80},
        "state_match_min": 60,
        "typo_fuzzy_min": 85,
        "lru_cache_ttl_s": 900,
    }


# Nominatim rate limiter (global, thread-safe)
_nom_lock = asyncio.Lock()
_nom_last_call = 0.0


async def _nom_rate_limit() -> None:
    global _nom_last_call
    cfg = get_geo_config()
    min_interval = cfg.get("nominatim", {}).get("min_interval_s", 1.05)
    async with _nom_lock:
        now = time.monotonic()
        wait = min_interval - (now - _nom_last_call)
        if wait > 0:
            await asyncio.sleep(wait)
        _nom_last_call = time.monotonic()


# In-Memory LRU Cache (Tier 0)
_IN_MEM_CACHE: dict[str, tuple[float, GeoResolution]] = {}


def _norm_str(s: str | None) -> str:
    if not s:
        return ""
    norm = unicodedata.normalize("NFKC", s).casefold()
    for p in [",", ".", ";", ":", "-", "_", "/", "'", '"', "(", ")", "[", "]", "{", "}"]:
        norm = norm.replace(p, " ")
    return " ".join(norm.split())


def _calc_cache_key(loc: LocationInput) -> str:
    d = {
        "locality": _norm_str(loc.locality),
        "city": _norm_str(loc.city),
        "state": _norm_str(loc.state),
        "country": _norm_str(loc.country or "India"),
        "raw_text": _norm_str(loc.raw_text),
    }
    return hashlib.sha256(json.dumps(d, sort_keys=True).encode()).hexdigest()


# Ground-Width Accurate Polygon Buffering (Tier 6)
def buffer_point_in_meters(lon: float, lat: float, radius_m: float, num_points: int = 32) -> Polygon:
    """Constructs a true-ground-width circular polygon at any latitude by scaling longitude by cos(latitude)."""
    lat_rad = math.radians(lat)
    cos_lat = max(0.01, math.cos(lat_rad))
    m_per_deg_lat = 111320.0
    m_per_deg_lon = 111320.0 * cos_lat
    coords = []
    for i in range(num_points):
        theta = 2.0 * math.pi * i / num_points
        dx = radius_m * math.cos(theta)
        dy = radius_m * math.sin(theta)
        p_lon = lon + (dx / m_per_deg_lon)
        p_lat = lat + (dy / m_per_deg_lat)
        coords.append((p_lon, p_lat))
    coords.append(coords[0])
    return Polygon(coords)


def _buffer_for_target(locality: bool, max_results: int = 100) -> int:
    cfg = get_geo_config()
    table = cfg.get("buffer_by_result_target", {})
    key = "locality" if locality else "city"
    entries = table.get(key, [])
    for entry in entries:
        if max_results <= entry.get("max_results", 5000):
            return int(entry.get("buffer_m", 1500))
    return int(cfg.get("buffers_m", {}).get("default", 1500))


def _calc_confidence(
    name_match_score: float,
    subtype: str,
    state_match: bool,
    n_competitors: int,
) -> float:
    cfg = get_geo_config()
    subtype_weights = cfg.get("subtype_weights", {})
    sub_weight = subtype_weights.get(subtype, 0.6)
    base = (
        name_match_score * 0.4
        + sub_weight * 0.3
        + (0.2 if state_match else 0.0)
        + max(0.0, 0.1 - 0.02 * n_competitors)
    )
    return min(1.0, max(0.0, base))


# Geographic Aliases and Contractions Loader
ALIASES_FILE = Path(__file__).resolve().parent.parent.parent.parent / "config" / "geo_aliases.yaml"
_CACHED_ALIASES: dict[str, Any] = {}


def _load_geo_aliases() -> dict[str, Any]:
    global _CACHED_ALIASES
    if _CACHED_ALIASES:
        return _CACHED_ALIASES
    if ALIASES_FILE.exists():
        try:
            data = yaml.safe_load(ALIASES_FILE.read_text(encoding="utf-8")) or {}
            _CACHED_ALIASES = {k.lower(): v for k, v in data.get("aliases", {}).items()}
        except Exception as exc:
            logger.warning(f"Failed to load geo aliases: {exc}")
            _CACHED_ALIASES = {}
    return _CACHED_ALIASES

_ = _load_geo_aliases()


# Disk Seeds Loader
SEEDS_FILE = Path(__file__).resolve().parent.parent.parent.parent / "seeds" / "areas.json"
_CACHED_SEEDS: list[dict[str, Any]] = []


def _load_seeds_from_disk() -> list[dict[str, Any]]:
    global _CACHED_SEEDS
    if _CACHED_SEEDS:
        return _CACHED_SEEDS
    if SEEDS_FILE.exists():
        try:
            _CACHED_SEEDS = json.loads(SEEDS_FILE.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning(f"Failed to load seeds from disk: {exc}")
            _CACHED_SEEDS = []
    return _CACHED_SEEDS

_ = _load_seeds_from_disk()  # Pre-warm seeds on module import


# Nominatim Search (Max 2 requests: 1 structured + 1 optional fallback)
async def _nominatim_search(loc: LocationInput) -> list[dict[str, Any]]:
    cfg = get_geo_config()
    nom_cfg = cfg.get("nominatim", {})
    timeout_s = nom_cfg.get("timeout_s", 8.0)
    max_res = nom_cfg.get("max_structured_results", 8)

    locality = (loc.locality or "").strip()
    city = (loc.city or "").strip()
    state = (loc.state or "").strip()
    country = (loc.country or "India").strip()
    target = locality or city or loc.raw_text or ""

    # Minimum-length guard: inputs under 4 characters go strictly to aliases / seeds, never to Nominatim
    if len(target) < 4:
        return []

    headers = {
        "User-Agent": f"{settings.crawler_user_agent} (contact: {settings.contact_email})",
        "Accept": "application/json",
    }

    # Request 1: Exactly ONE structured query
    poly_thresh = nom_cfg.get("polygon_threshold")
    params: dict[str, Any] = {
        "city": city or None,
        "state": state or None,
        "country": country,
        "q": locality or None,
        "format": "geojson",
        "addressdetails": 1,
        "namedetails": 1,
        "extratags": 1,
        "polygon_geojson": 1,
        "polygon_threshold": poly_thresh,
        "limit": max_res,
    }
    if country.lower() in ("india", "in"):
        params["countrycodes"] = "in"

    params = {k: v for k, v in params.items() if v is not None}
    results: list[dict[str, Any]] = []
    await _nom_rate_limit()

    try:
        async with httpx.AsyncClient(timeout=timeout_s, headers=headers) as client:
            r = await client.get(f"{settings.nominatim_url}/search", params=params)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, dict) and "features" in data:
                    return data.get("features", [])
                elif isinstance(data, list) and data:
                    return data
    except Exception as e:
        logger.warning(f"Nominatim structured query warning: {e}")

    # Request 2 (Fallback only if structured query returned nothing)
    fallback_q = f"{locality} {city} {state} {country}".strip()
    if fallback_q:
        await _nom_rate_limit()
        fb_params = {
            "q": fallback_q,
            "format": "geojson",
            "addressdetails": 1,
            "namedetails": 1,
            "extratags": 1,
            "polygon_geojson": 1,
            "polygon_threshold": poly_thresh,
            "limit": max_res,
        }
        if country.lower() in ("india", "in"):
            fb_params["countrycodes"] = "in"
        try:
            async with httpx.AsyncClient(timeout=timeout_s, headers=headers) as client:
                r = await client.get(f"{settings.nominatim_url}/search", params=fb_params)
                if r.status_code == 200:
                    data = r.json()
                    if isinstance(data, dict) and "features" in data:
                        return data.get("features", [])
                    elif isinstance(data, list) and data:
                        return data
        except Exception as e:
            logger.warning(f"Nominatim fallback query warning: {e}")

    return results


# Photon Fallback Geocoder (Tier 5)
async def _photon_search(loc: LocationInput) -> list[dict[str, Any]]:
    cfg = get_geo_config()
    timeout_s = cfg.get("photon", {}).get("timeout_s", 8.0)
    limit = cfg.get("photon", {}).get("max_results", 5)

    target = f"{loc.locality or ''} {loc.city or ''} {loc.state or ''}".strip() or loc.raw_text or ""
    if not target:
        return []

    headers = {
        "User-Agent": f"{settings.crawler_user_agent} (contact: {settings.contact_email})",
    }
    try:
        async with httpx.AsyncClient(timeout=timeout_s, headers=headers) as client:
            r = await client.get(f"{settings.photon_url}/api", params={"q": target, "limit": limit})
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, dict):
                    features = data.get("features", [])
                    if features:
                        return list(features)
    except Exception as e:
        logger.warning(f"Photon search warning: {e}")
    return []


def _query_overture_divisions(loc: LocationInput) -> GeoResolution | None:
    """Tier 3: Query local Overture division polygons using DuckDB spatial."""
    try:
        divisions_dir = settings.overture_cache_dir / "divisions"
        if not divisions_dir.exists():
            return None
        parquets = list(divisions_dir.glob("*.parquet"))
        if not parquets:
            return None

        locality = (loc.locality or "").strip()
        city = (loc.city or "").strip()
        state = (loc.state or "").strip()
        target = locality or city
        if not target:
            return None

        con = duckdb.connect()
        con.execute("INSTALL spatial; LOAD spatial;")
        parquet_path = str(parquets[0]).replace("\\", "/")

        query = f"""
            SELECT ST_AsText(geometry) as wkt, names.primary as name, subtype
            FROM read_parquet('{parquet_path}')
            WHERE lower(names.primary) = lower(?)
            LIMIT 1
        """
        res = con.execute(query, [target]).fetchone()
        if res and res[0]:
            wkt_poly, name_matched, subtype = res[0], res[1], res[2]
            geom = shapely.wkt.loads(wkt_poly)
            bounds = geom.bounds
            centroid = geom.centroid
            disp = f"{name_matched}, {city or ''}, {state or ''}, {loc.country or 'India'}".strip(", ")
            return GeoResolution(
                display_name=disp,
                osm_id=f"overture/division/{name_matched}",
                polygon_wkt=wkt_poly,
                boundary_geojson=mapping(geom),
                boundary_kind="division_polygon",
                boundary_source="overture_division_area",
                bbox=(bounds[0], bounds[1], bounds[2], bounds[3]),
                centroid=(centroid.x, centroid.y),
                geo_confidence=0.95,
                alternatives=[],
            )
    except Exception as e:
        logger.debug(f"Overture divisions lookup fallback: {e}")
    return None


# Main 7-Tier Resolver
async def resolve_location(loc: LocationInput, max_results: int = 100) -> GeoResolution:
    """Resolve a LocationInput through the 7-Tier Resolution Ladder."""
    cfg = get_geo_config()
    # Alias / Abbreviation expansion (e.g., 'hsr' -> 'HSR Layout', 'blr' -> 'Bengaluru')
    aliases = get_geo_aliases()
    raw_key = (loc.locality or loc.city or loc.raw_text or "").strip().lower()
    if raw_key in aliases:
        alias_data = aliases[raw_key]
        if isinstance(alias_data, dict):
            loc = LocationInput(
                locality=alias_data.get("locality") or loc.locality,
                city=alias_data.get("city") or loc.city,
                state=alias_data.get("state") or loc.state,
                country=alias_data.get("country") or loc.country or "India",
                raw_text=loc.raw_text,
                lat=loc.lat,
                lon=loc.lon,
                radius_m=loc.radius_m,
            )

    if loc.locality and loc.locality.strip().lower() in aliases:
        l_alias = aliases[loc.locality.strip().lower()]
        if isinstance(l_alias, dict):
            loc = loc.model_copy(update={
                "locality": l_alias.get("locality") or loc.locality,
                "city": l_alias.get("city") or loc.city,
                "state": l_alias.get("state") or loc.state,
            })

    if loc.city and loc.city.strip().lower() in aliases:
        c_alias = aliases[loc.city.strip().lower()]
        if isinstance(c_alias, dict):
            loc = loc.model_copy(update={
                "city": c_alias.get("city") or loc.city,
                "state": c_alias.get("state") or loc.state,
            })

    locality = (loc.locality or "").strip()
    city = (loc.city or "").strip()
    state_hint = (loc.state or "").strip()
    country = (loc.country or "India").strip()
    target = locality or city or loc.raw_text or ""

    # Direct Lat / Lon coordinates provided
    if loc.lat is not None and loc.lon is not None:
        buf_m = int(loc.radius_m) if loc.radius_m else _buffer_for_target(bool(locality), max_results)
        geom = buffer_point_in_meters(loc.lon, loc.lat, buf_m)
        bounds = geom.bounds
        disp = locality or loc.raw_text or f"Custom Coord ({loc.lat:.4f}, {loc.lon:.4f})"
        return GeoResolution(
            display_name=f"{disp}, {city or ''}, {state_hint or ''}, {country}".strip(", "),
            osm_id="custom_coords",
            polygon_wkt=geom.wkt,
            boundary_kind="buffered_point",
            buffer_m=buf_m,
            bbox=(bounds[0], bounds[1], bounds[2], bounds[3]),
            centroid=(loc.lon, loc.lat),
            geo_confidence=1.0,
            alternatives=[],
        )

    buf_m = _buffer_for_target(bool(locality), max_results)
    cache_key = _calc_cache_key(loc)

    # Tier 0: In-Memory LRU Cache (< 1ms)
    now = time.monotonic()
    ttl = float(cfg.get("lru_cache_ttl_s", 900))
    if cache_key in _IN_MEM_CACHE:
        cached_time, cached_geo = _IN_MEM_CACHE[cache_key]
        if (now - cached_time) < ttl:
            return cached_geo

    # Tier 2 (Offline seeds + RapidFuzz Typo Handling - executed first for instant ~2ms resolution)
    typo_min = cfg.get("typo_fuzzy_min", 85)
    disk_seeds = _load_seeds_from_disk()
    best_seed_match: dict[str, Any] | None = None
    best_seed_score = 0.0
    alt_seed_matches: list[dict[str, Any]] = []

    for city_group in disk_seeds:
        c_name = city_group.get("city", "")
        c_state = city_group.get("state", "")
        city_match_score = fuzz.token_set_ratio((city or target).lower(), c_name.lower())

        # Check city-level match if no specific locality is provided
        if not locality and city_match_score >= typo_min:
            areas = city_group.get("areas", [])
            if areas and areas[0].get("centroid"):
                c_lon, c_lat = areas[0]["centroid"][0], areas[0]["centroid"][1]
                c_bbox = areas[0].get("bbox")
                c_geom = box(*c_bbox) if c_bbox else buffer_point_in_meters(c_lon, c_lat, buf_m)
                c_bounds = c_geom.bounds
                c_res = GeoResolution(
                    display_name=f"{c_name}, {c_state}, {country}".strip(", "),
                    osm_id=f"seed/city/{c_name}",
                    polygon_wkt=c_geom.wkt,
                    boundary_geojson=mapping(c_geom),
                    boundary_kind="admin_polygon" if c_bbox else "buffered_point",
                    boundary_source="osm_relation" if c_bbox else "radius_circle",
                    buffer_m=buf_m if not c_bbox else None,
                    bbox=(c_bounds[0], c_bounds[1], c_bounds[2], c_bounds[3]),
                    centroid=(c_lon, c_lat),
                    geo_confidence=0.95,
                    alternatives=[],
                )
                _IN_MEM_CACHE[cache_key] = (now, c_res)
                return c_res

        if city and city_match_score < 70 and city.lower() not in c_name.lower() and c_name.lower() not in city.lower():
            continue

        for a in city_group.get("areas", []):
            loc_name = a.get("locality", "")
            match_score = fuzz.token_set_ratio(target.lower(), loc_name.lower())
            if target.lower() == loc_name.lower():
                match_score = 100.0
            if match_score >= typo_min:
                seed_item: dict[str, Any] = {
                    "locality": loc_name,
                    "city": c_name,
                    "state": c_state,
                    "centroid": a.get("centroid", []),
                    "bbox": a.get("bbox"),
                    "score": match_score,
                }
                if match_score > best_seed_score:
                    best_seed_score = match_score
                    best_seed_match = seed_item
                else:
                    alt_seed_matches.append(seed_item)

    if best_seed_match:
        centroid_val = best_seed_match.get("centroid")
        if isinstance(centroid_val, list) and len(centroid_val) >= 2:
            lon = float(centroid_val[0])
            lat = float(centroid_val[1])
            s_bbox = best_seed_match.get("bbox")
            if isinstance(s_bbox, list) and len(s_bbox) == 4:
                geom = box(float(s_bbox[0]), float(s_bbox[1]), float(s_bbox[2]), float(s_bbox[3]))
                b_kind = "admin_polygon"
                b_source = "osm_relation"
            else:
                geom = buffer_point_in_meters(lon, lat, buf_m)
                b_kind = "buffered_point"
                b_source = "radius_circle"

        bounds = geom.bounds
        matched_loc = best_seed_match["locality"]
        matched_city = best_seed_match["city"]
        matched_state = best_seed_match["state"]
        disp = f"{matched_loc}, {matched_city}, {matched_state}, {country}".strip(", ")
        geo_res = GeoResolution(
            display_name=disp,
            osm_id=f"seed/{matched_loc}",
            polygon_wkt=geom.wkt,
            boundary_geojson=mapping(geom),
            boundary_kind=b_kind,
            boundary_source=b_source,
            buffer_m=buf_m if b_kind == "buffered_point" else None,
            bbox=(bounds[0], bounds[1], bounds[2], bounds[3]),
            centroid=(lon, lat),
            geo_confidence=0.96 if best_seed_score == 100.0 else 0.92,
            alternatives=[
                {"display_name": f"{alt['locality']}, {alt['city']}, {alt['state']}", "osm_id": f"seed/{alt['locality']}"}
                for alt in alt_seed_matches[:4]
            ],
        )
        _IN_MEM_CACHE[cache_key] = (now, geo_res)
        return geo_res

    # Tier 1: Postgres geo_cache Table (~20ms)
    try:
        async with get_conn() as conn:
            cached_row = await (await conn.execute(
                "SELECT response FROM geo_cache WHERE query_hash = %s", (cache_key,)
            )).fetchone()
            if cached_row:
                raw_val = cached_row["response"]
                data = json.loads(raw_val) if isinstance(raw_val, str) else raw_val
                if isinstance(data, dict) and "polygon_wkt" in data:
                    geo = GeoResolution(**data)
                    _IN_MEM_CACHE[cache_key] = (now, geo)
                    return geo
    except Exception:
        pass

    # Tier 3: Overture Divisions Parquet (DuckDB Spatial, 100-400ms)
    division_geo = _query_overture_divisions(loc)
    if division_geo:
        _IN_MEM_CACHE[cache_key] = (now, division_geo)
        return division_geo

    # Tier 4: Nominatim (Single Structured Query + Local Ranking)
    candidates = await _nominatim_search(loc)
    best_candidate = None
    best_cand_score = 0.0
    penalties = cfg.get("penalties", {})
    city_pen = penalties.get("city_mismatch", 0.60)
    state_pen = penalties.get("state_mismatch", 0.80)
    state_min = cfg.get("state_match_min", 60)

    for item in candidates:
        if isinstance(item, dict) and "properties" in item:
            props = item["properties"]
            disp = props.get("display_name", "")
            addr = props.get("address", {})
            item_state = addr.get("state", "")
        else:
            props = item
            disp = item.get("display_name", "")
            addr = item.get("address", {})
            item_state = addr.get("state", "")

        name_in_resp = addr.get("suburb") or addr.get("neighbourhood") or addr.get("village") or addr.get("city") or disp
        score = fuzz.token_sort_ratio(target.lower(), name_in_resp.lower()) / 100.0
        if locality:
            loc_score = fuzz.partial_ratio(locality.lower(), disp.lower()) / 100.0
            score = max(score, loc_score)
        if city and city.lower() not in disp.lower() and city.lower() not in addr.get("city", "").lower() and city.lower() not in addr.get("state_district", "").lower():
            score *= city_pen
        state_match = (
            not state_hint
            or fuzz.partial_ratio(state_hint.lower(), item_state.lower()) >= state_min
        )
        if not state_match:
            score *= state_pen
        if score > best_cand_score:
            best_cand_score = score
            best_candidate = item

    accept_thresh = cfg.get("accept_threshold", {})
    min_score = accept_thresh.get("with_locality", 0.55) if locality else accept_thresh.get("without_locality", 0.50)

    if best_candidate and best_cand_score >= min_score:
        if isinstance(best_candidate, dict) and "properties" in best_candidate:
            props = best_candidate["properties"]
            geom_json = best_candidate.get("geometry")
            disp_name = props.get("display_name", "")
            osm_type = str(props.get("osm_type", "")).lower()
            osm_id_val = str(props.get("osm_id", "0"))
            c_coords = geom_json.get("coordinates") if geom_json else None
            lat = float(c_coords[1]) if geom_json and geom_json.get("type") == "Point" and len(c_coords) >= 2 else float(props.get("lat", 0.0))
            lon = float(c_coords[0]) if geom_json and geom_json.get("type") == "Point" and len(c_coords) >= 2 else float(props.get("lon", 0.0))
        else:
            props = best_candidate
            geom_json = best_candidate.get("geojson")
            disp_name = best_candidate.get("display_name", "")
            osm_type = str(best_candidate.get("osm_type", "")).lower()
            osm_id_val = str(best_candidate.get("osm_id", "0"))
            lat = float(best_candidate.get("lat", 0.0))
            lon = float(best_candidate.get("lon", 0.0))

        geom = None
        boundary_kind = "admin_polygon"
        boundary_source = "osm_relation"

        if geom_json and geom_json.get("type") in ("Polygon", "MultiPolygon"):
            try:
                g_parsed = shape(geom_json)
                if g_parsed.is_valid and not g_parsed.is_empty:
                    geom = g_parsed
                    boundary_kind = "admin_polygon"
                    boundary_source = "osm_way" if osm_type == "way" else "osm_relation"
            except Exception as e:
                logger.warning(f"GeoJSON shape parse fallback: {e}")
                geom = None

        if geom is None:
            geom = buffer_point_in_meters(lon, lat, buf_m)
            boundary_kind = "buffered_point"
            boundary_source = "radius_circle"

        centroid = geom.centroid
        bounds = geom.bounds
        disp_title = locality or disp_name.split(",")[0]
        geo_res = GeoResolution(
            display_name=f"{disp_title}, {city or ''}, {state_hint or ''}, {country}".strip(", "),
            osm_id=osm_id_val,
            polygon_wkt=geom.wkt,
            boundary_geojson=mapping(geom),
            boundary_kind=boundary_kind,
            boundary_source=boundary_source,
            buffer_m=buf_m if boundary_kind == "buffered_point" else None,
            bbox=(bounds[0], bounds[1], bounds[2], bounds[3]),
            centroid=(centroid.x, centroid.y),
            geo_confidence=max(0.85, best_cand_score),
            alternatives=[
                {
                    "display_name": (c.get("properties", {}).get("display_name") if "properties" in c else c.get("display_name")),
                    "osm_id": str(c.get("properties", {}).get("osm_id") if "properties" in c else c.get("osm_id", ""))
                }
                for c in candidates if c is not best_candidate
            ][:5],
        )
        _IN_MEM_CACHE[cache_key] = (now, geo_res)
        try:
            async with get_conn() as conn:
                await conn.execute(
                    "INSERT INTO geo_cache (query_hash, provider, response) VALUES (%s, 'nominatim', %s) ON CONFLICT (query_hash) DO NOTHING",
                    (cache_key, json.dumps(geo_res.model_dump())),
                )
                await conn.commit()
        except Exception:
            pass
        return geo_res

    # Tier 5: Photon Fallback
    photon_features = await _photon_search(loc)
    for feat in photon_features:
        props = feat.get("properties", {})
        coords = feat.get("geometry", {}).get("coordinates", [])
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
        if score >= 0.45:
            geom = buffer_point_in_meters(lon, lat, buf_m)
            bounds = geom.bounds
            geo_res = GeoResolution(
                display_name=f"{locality or name}, {city or f_city}, {state_hint or f_state}, {country}".strip(", "),
                osm_id=str(props.get("osm_id", "photon")),
                polygon_wkt=geom.wkt,
                boundary_geojson=mapping(geom),
                boundary_kind="buffered_point",
                boundary_source="radius_circle",
                buffer_m=buf_m,
                bbox=(bounds[0], bounds[1], bounds[2], bounds[3]),
                centroid=(lon, lat),
                geo_confidence=0.80,
                alternatives=[],
            )
            _IN_MEM_CACHE[cache_key] = (now, geo_res)
            return geo_res

    # Tier 6: Default Centroid Fallback (Proper Cosine Projection)
    lon, lat = (78.456, 17.420) if "hyderabad" in (city.lower() + locality.lower()) else (77.624, 12.935)
    geom = buffer_point_in_meters(lon, lat, buf_m)
    bounds = geom.bounds
    geo_res = GeoResolution(
        display_name=f"{target}, {city or 'Bengaluru'}, {state_hint or 'Karnataka'}, {country}".strip(", "),
        osm_id="fallback",
        polygon_wkt=geom.wkt,
        boundary_geojson=mapping(geom),
        boundary_kind="buffered_point",
        boundary_source="radius_circle",
        buffer_m=buf_m,
        bbox=(bounds[0], bounds[1], bounds[2], bounds[3]),
        centroid=(lon, lat),
        geo_confidence=0.60,
        alternatives=[],
    )
    _IN_MEM_CACHE[cache_key] = (now, geo_res)
    return geo_res


# Disambiguation interrupt node
async def disambiguation_interrupt(state: RunState) -> dict[str, Any]:
    geo = state.get("geo")
    alternatives: list[dict[str, Any]] = geo.alternatives if geo else []
    choice = interrupt({
        "type": "disambiguation",
        "message": "Multiple areas matched. Please pick one.",
        "alternatives": alternatives,
    })
    return {"disambiguation_choice": choice}


# LangGraph node entry point
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
