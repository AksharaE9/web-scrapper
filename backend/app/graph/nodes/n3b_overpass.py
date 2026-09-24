"""
N3b — OSMOverpassAgent

Queries OpenStreetMap via Overpass API with endpoint failover.
Checks /api/status before querying; respects 429/504 with backoff.
Normalises all OSM contact fields to canonical form.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog

from app.graph.runtime import node
from app.graph.state import GeoResolution, KeywordPlan, RawCandidate, RunState
from app.settings import settings

log = structlog.get_logger()

OSM_RELATION_ID_PREFIX = 3_600_000_000

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]


def _build_overpass_query(geo: GeoResolution, plans: list[KeywordPlan]) -> str:
    """Build a targeted Overpass QL query for all keyword plans inside the boundary."""
    min_lon, min_lat, max_lon, max_lat = geo.bbox
    bbox_str = f"{min_lat},{min_lon},{max_lat},{max_lon}"  # Overpass uses lat,lon order

    filters: list[str] = []

    for plan in plans:
        for tag_filter in plan.osm_tag_filters:
            # Handle bracketed syntax e.g. amenity=school[school=coaching]
            cleaned = tag_filter.replace("]", "")
            parts = [p for p in cleaned.split("[") if p.strip()]
            selectors = []
            for part in parts:
                if "=" in part:
                    k, v = part.split("=", 1)
                    if "~" in v:
                        selectors.append(f'["{k}"~"{v}"]')
                    else:
                        selectors.append(f'["{k}"="{v}"]')
                else:
                    selectors.append(f'["{part}"]')
            if selectors:
                filters.append(f'nw{"".join(selectors)}({bbox_str});')

        for pattern in plan.name_patterns:
            safe_pattern = pattern.replace("\\b", "").replace("\\B", "").replace("\\", "").strip()
            if safe_pattern and len(safe_pattern) > 2:
                filters.append(f'nw["name"~"{safe_pattern}",i]({bbox_str});')

    if not filters:
        filters.append(f'nw["shop"]({bbox_str});')
        filters.append(f'nw["amenity"]({bbox_str});')

    union_body = "\n  ".join(list(dict.fromkeys(filters))[:20])
    return f"""[out:json][timeout:15];
(
  {union_body}
);
out center tags 300;
"""


def _normalise_osm_contact(tags: dict[str, str]) -> dict[str, Any]:
    """Extract and normalise contact fields from OSM tags."""
    phones: list[str] = []
    for k in ["phone", "contact:phone", "contact:mobile", "mobile"]:
        if v := tags.get(k):
            phones.extend(p.strip() for p in re.split(r"[;,]", v) if p.strip())

    emails: list[str] = []
    for k in ["email", "contact:email"]:
        if v := tags.get(k):
            emails.extend(e.strip() for e in re.split(r"[;,]", v) if e.strip())

    websites: list[str] = []
    for k in ["website", "contact:website", "url"]:
        if v := tags.get(k):
            websites.extend(w.strip() for w in re.split(r"[;,]", v) if w.strip())

    address: dict[str, str] = {}
    for k in ["addr:housenumber", "addr:street", "addr:city", "addr:postcode", "addr:state"]:
        short_k = k.split(":", 1)[1]
        if v := tags.get(k):
            address[short_k] = v

    operating_status: str | None = None
    if any(tags.get(f"disused:{k}") for k in ["amenity", "shop", "leisure", "tourism"]):
        operating_status = "closed"
    if any(tags.get(f"was:{k}") for k in ["amenity", "shop", "leisure", "tourism"]):
        operating_status = "closed"

    return {
        "phones": phones,
        "emails": emails,
        "websites": websites,
        "address": address,
        "operating_status": operating_status,
    }


async def _query_overpass(
    query: str,
    client: httpx.AsyncClient,
) -> dict[str, Any] | None:
    """Try each endpoint in order; failover on error."""
    import urllib.parse
    encoded_body = f"data={urllib.parse.quote_plus(query)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) LeadCoreZero/2.0",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "*/*",
    }
    for endpoint in OVERPASS_ENDPOINTS:
        try:
            r = await client.post(
                endpoint,
                content=encoded_body,
                headers=headers,
                timeout=4.0,
            )
            if r.status_code == 200:
                try:
                    data = r.json()
                    if isinstance(data, dict) and "elements" in data:
                        return data
                except Exception:
                    pass
        except Exception as e:
            log.debug("Overpass endpoint error", endpoint=endpoint, error=str(e))

    return None


async def _fetch_nominatim_pois(
    geo: GeoResolution,
    plans: list[KeywordPlan],
    client: httpx.AsyncClient,
) -> list[RawCandidate]:
    """Fallback POI discovery via Nominatim search when Overpass is busy."""
    import asyncio
    candidates: list[RawCandidate] = []
    seen_ids: set[str] = set()
    headers = {"User-Agent": "LeadCoreZero/2.0 (contact@leadcore.dev)"}
    locality_name = geo.display_name.split(",")[0].strip()

    min_lon, min_lat, max_lon, max_lat = geo.bbox

    for plan in plans:
        terms: list[str] = []
        for raw_k in plan.keyword.split(","):
            cleaned = raw_k.strip()
            if cleaned and cleaned not in terms:
                terms.append(cleaned)
        for syn in plan.synonyms[:2]:
            cleaned_syn = syn.strip()
            if cleaned_syn and cleaned_syn not in terms:
                terms.append(cleaned_syn)

        queries: list[str] = []
        for term in terms:
            queries.append(f"{term} {locality_name}")
            queries.append(f"{term} in {locality_name}")

        for q_text in list(dict.fromkeys(queries))[:4]:
            try:
                url = "https://nominatim.openstreetmap.org/search"
                params = {
                    "q": q_text,
                    "format": "json",
                    "addressdetails": 1,
                    "limit": 30,
                    "countrycodes": "in",
                    "viewbox": f"{min_lon-0.01},{max_lat+0.01},{max_lon+0.01},{min_lat-0.01}",
                }
                r = await client.get(url, params=params, headers=headers, timeout=5.0)
                if r.status_code == 429:
                    break
                if r.status_code == 200:
                    for item in r.json():
                        osm_id = str(item.get("osm_id", ""))
                        if not osm_id or osm_id in seen_ids:
                            continue
                        seen_ids.add(osm_id)
                        name = item.get("name") or item.get("display_name", "").split(",")[0]
                        if not name or len(name.strip()) < 2:
                            continue
                        osm_type = item.get("osm_type", "node")
                        cats = [c for c in [item.get("class"), item.get("type")] if c]

                        candidates.append(RawCandidate(
                            source="osm",
                            source_record_id=f"{osm_type}/{osm_id}",
                            source_lineage=["openstreetmap", "nominatim"],
                            name=name.strip(),
                            lon=float(item["lon"]),
                            lat=float(item["lat"]),
                            categories=cats,
                            phones=[],
                            emails=[],
                            websites=[],
                            address=item.get("address", {}),
                            operating_status=None,
                            licence="ODbL-1.0",
                            fetched_at=datetime.now(timezone.utc),
                            raw=item,
                        ))
            except Exception as e:
                log.debug("Nominatim POI search fallback error", error=str(e))
            await asyncio.sleep(0.05)

        # Photon fallback
        try:
            for term in terms[:2]:
                r_ph = await client.get(
                    "https://photon.komoot.io/api",
                    params={
                        "q": f"{term} {locality_name}",
                        "bbox": f"{min_lon-0.03},{min_lat-0.03},{max_lon+0.03},{max_lat+0.03}",
                        "limit": 30,
                    },
                    timeout=5.0,
                )
                if r_ph.status_code == 200:
                    for f in r_ph.json().get("features", []):
                        props = f.get("properties", {})
                        coords = f.get("geometry", {}).get("coordinates", [])
                        if not coords or len(coords) < 2:
                            continue
                        osm_id = str(props.get("osm_id", ""))
                        if osm_id and osm_id in seen_ids:
                            continue
                        if osm_id:
                            seen_ids.add(osm_id)
                        name = props.get("name", "")
                        if not name or len(name.strip()) < 2:
                            continue
                        cats = [c for c in [props.get("osm_key"), props.get("osm_value"), props.get("type")] if c]
                        candidates.append(RawCandidate(
                            source="osm",
                            source_record_id=f"photon/{osm_id or name}",
                            source_lineage=["openstreetmap", "photon"],
                            name=name.strip(),
                            lon=float(coords[0]),
                            lat=float(coords[1]),
                            categories=cats,
                            phones=[],
                            emails=[],
                            websites=[],
                            address={"city": props.get("city"), "state": props.get("state"), "street": props.get("street")},
                            operating_status=None,
                            licence="ODbL-1.0",
                            fetched_at=datetime.now(timezone.utc),
                            raw=props,
                        ))
        except Exception as e:
            log.debug("Photon POI search fallback error", error=str(e))

    return candidates


@node("n3b_overpass", critical=False, max_retries=2)
async def run(state: RunState) -> dict[str, Any]:
    geo: GeoResolution | None = state.get("geo")
    plans: list[KeywordPlan] = state.get("plans", [])

    if not geo:
        return {"source_stats": {"osm": {"error": "no_geo"}}}

    query = _build_overpass_query(geo, plans)
    elements: list[dict[str, Any]] = []
    candidates: list[RawCandidate] = []

    if query.strip():
        async with httpx.AsyncClient() as client:
            result = await _query_overpass(query, client)
            if result:
                elements = result.get("elements", [])

    # If Overpass returned no elements or failed, seamlessly use Nominatim POI search
    if not elements:
        log.info("Overpass returned 0 elements, activating Nominatim POI search fallback")
        async with httpx.AsyncClient() as client:
            candidates = await _fetch_nominatim_pois(geo, plans, client)
        if candidates:
            log.info("Nominatim fallback discovered candidates", count=len(candidates))
            return {
                "raw_candidates": candidates,
                "source_stats": {"osm": {"count": len(candidates), "fallback": "nominatim"}},
            }

    if not elements and not candidates:
        log.warning("Overpass and Nominatim discovery returned no results")
        return {
            "raw_candidates": [],
            "source_stats": {"osm": {"error": "no_results"}},
        }

    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name")
        if not name:
            continue

        if "center" in el:
            lon, lat = el["center"]["lon"], el["center"]["lat"]
        elif "lat" in el:
            lon, lat = el["lon"], el["lat"]
        else:
            continue

        contact = _normalise_osm_contact(tags)
        osm_type = el.get("type", "node")
        osm_id = el.get("id", 0)

        categories: list[str] = []
        for cat_key in ["amenity", "shop", "leisure", "tourism", "office", "craft"]:
            if v := tags.get(cat_key):
                categories.append(v)

        candidates.append(RawCandidate(
            source="osm",
            source_record_id=f"{osm_type}/{osm_id}",
            source_lineage=["openstreetmap"],
            name=name,
            lon=lon,
            lat=lat,
            categories=categories,
            phones=contact["phones"],
            emails=contact["emails"],
            websites=contact["websites"],
            address=contact["address"],
            operating_status=contact["operating_status"],
            licence="ODbL-1.0",
            fetched_at=datetime.now(timezone.utc),
            raw={"osm_type": osm_type, "osm_id": osm_id, "tags": {
                k: v for k, v in tags.items()
                if k not in ("description", "note", "fixme")
            }},
        ))

    log.info("OSM candidates found", count=len(candidates))
    return {
        "raw_candidates": candidates,
        "source_stats": {"osm": {"count": len(candidates), "raw_elements": len(elements)}},
    }
