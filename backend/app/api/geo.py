"""Geo API — autocomplete, boundary resolution, boundary preview."""

from __future__ import annotations

import hashlib
import json
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.db.pool import get_conn
from app.settings import settings

router = APIRouter(tags=["geo"])


class GeoSuggestion(BaseModel):
    display_name: str
    locality: str | None
    city: str | None
    state: str | None
    country: str
    source: str  # area_seeds | geo_cache | nominatim


class BoundaryPreview(BaseModel):
    display_name: str
    boundary_geojson: dict[str, Any] | None
    boundary_kind: str
    geo_confidence: float
    centroid_lon: float | None
    centroid_lat: float | None
    alternatives: list[dict[str, Any]]


@router.get("/geo/suggest", response_model=list[GeoSuggestion])
async def geo_suggest(
    q: str = Query(..., min_length=2),
    state: str | None = None,
    country: str = "India",
    limit: int = 10,
) -> list[GeoSuggestion]:
    """
    Autocomplete location suggestions.
    Priority: area_seeds (trigram match) → geo_cache → Nominatim (rate-limited, debounced server-side).
    """
    results: list[GeoSuggestion] = []
    params: list[Any] = [f"%{q}%", limit]

    # 1. Area seeds (trigram similarity)
    try:
        async with get_conn() as conn:
            rows = await (await conn.execute(
                """
                SELECT area, region, city FROM area_seeds
                WHERE area ILIKE %s
                ORDER BY similarity(area, %s) DESC
                LIMIT %s
                """,
                [f"%{q}%", q, limit],
            )).fetchall()

        for r in rows:
            results.append(GeoSuggestion(
                display_name=f"{r['area']}, {r['region']}, {r['city']}",
                locality=r["area"],
                city=r["city"],
                state=None,
                country=country,
                source="area_seeds",
            ))
    except Exception:
        pass

    if len(results) >= limit:
        return results[:limit]

    # 2. Nominatim (with caching — never hit Nominatim twice for the same query)
    cache_key = hashlib.sha256(f"nominatim:suggest:{q}:{state}:{country}".encode()).hexdigest()
    try:
        async with get_conn() as conn:
            cached = await (await conn.execute(
                "SELECT response FROM geo_cache WHERE query_hash = %s", (cache_key,)
            )).fetchone()

        if cached:
            for item in cached["response"].get("results", [])[:limit - len(results)]:
                results.append(GeoSuggestion(**item, source="geo_cache"))
            return results[:limit]
    except Exception:
        pass

    # Hit Nominatim (rate limited to 1 req/s in the calling code)
    try:
        params_nom: dict[str, Any] = {
            "q": q,
            "format": "json",
            "addressdetails": 1,
            "limit": 8,
            "countrycodes": "in" if country == "India" else "",
        }
        async with httpx.AsyncClient(
            timeout=10,
            headers={"User-Agent": settings.crawler_user_agent},
        ) as client:
            r = await client.get(f"{settings.nominatim_url}/search", params=params_nom)
        r.raise_for_status()
        items = r.json()

        nom_results = []
        for item in items:
            addr = item.get("address", {})
            sug = GeoSuggestion(
                display_name=item.get("display_name", ""),
                locality=addr.get("suburb") or addr.get("neighbourhood") or addr.get("village"),
                city=addr.get("city") or addr.get("town"),
                state=addr.get("state"),
                country=addr.get("country", country),
                source="nominatim",
            )
            nom_results.append(sug)
            results.append(sug)

        # Cache the result
        try:
            cache_payload = {"results": [s.model_dump() for s in nom_results]}
            async with get_conn() as conn:
                await conn.execute(
                    """
                    INSERT INTO geo_cache (query_hash, provider, response)
                    VALUES (%s, 'nominatim', %s)
                    ON CONFLICT (query_hash) DO NOTHING
                    """,
                    (cache_key, json.dumps(cache_payload)),
                )
                await conn.commit()
        except Exception:
            pass

    except Exception:
        pass  # Nominatim failure is non-fatal; return what we have from seeds

    return results[:limit]


@router.get("/geo/preview")
async def geo_preview_get(
    text: str | None = None,
    locality: str | None = None,
    city: str | None = None,
    state: str | None = None,
    country: str = "India",
) -> dict[str, Any]:
    """Preview geo boundary via GET query params (called by frontend)."""
    from app.graph.nodes.n1_geo import resolve_location
    from app.graph.state import LocationInput

    loc = LocationInput(
        raw_text=text,
        locality=locality,
        city=city,
        state=state,
        country=country,
    )
    try:
        geo = await resolve_location(loc)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    geojson = None
    try:
        import shapely.wkt
        from shapely.geometry import mapping
        geom = shapely.wkt.loads(geo.polygon_wkt)
        geojson = mapping(geom)
    except Exception:
        pass

    return {
        "display_name": geo.display_name,
        "osm_id": geo.osm_id,
        "overture_division_id": geo.overture_division_id,
        "polygon_wkt": geo.polygon_wkt,
        "boundary_geojson": geojson,
        "boundary_kind": geo.boundary_kind,
        "buffer_m": geo.buffer_m,
        "bbox": list(geo.bbox),
        "centroid": list(geo.centroid),
        "geo_confidence": geo.geo_confidence,
        "centroid_lon": geo.centroid[0] if geo.centroid else None,
        "centroid_lat": geo.centroid[1] if geo.centroid else None,
        "alternatives": geo.alternatives,
    }


@router.post("/geo/preview")
@router.post("/geo/resolve")
async def geo_resolve(body: dict[str, Any]) -> dict[str, Any]:
    """
    Preview the geo boundary for a location before creating a run.
    Calls N1 GeoResolverAgent logic directly.
    """
    from app.graph.nodes.n1_geo import resolve_location
    from app.graph.state import LocationInput

    loc = LocationInput(**body)
    try:
        geo = await resolve_location(loc)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    geojson = None
    try:
        import shapely.wkt
        from shapely.geometry import mapping
        geom = shapely.wkt.loads(geo.polygon_wkt)
        geojson = mapping(geom)
    except Exception:
        pass

    return {
        "display_name": geo.display_name,
        "osm_id": geo.osm_id,
        "overture_division_id": geo.overture_division_id,
        "polygon_wkt": geo.polygon_wkt,
        "boundary_geojson": geojson,
        "boundary_kind": geo.boundary_kind,
        "buffer_m": geo.buffer_m,
        "bbox": list(geo.bbox),
        "centroid": list(geo.centroid),
        "geo_confidence": geo.geo_confidence,
        "centroid_lon": geo.centroid[0] if geo.centroid else None,
        "centroid_lat": geo.centroid[1] if geo.centroid else None,
        "alternatives": geo.alternatives,
    }
