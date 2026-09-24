"""N3c — WikidataAgent (queries Wikidata SPARQL for institutions, brands, and entities)."""
from __future__ import annotations

import logging
from typing import Any
import httpx

from app.graph.runtime import node
from app.graph.state import RawCandidate, RunState
from app.settings import settings

logger = logging.getLogger(__name__)


@node("n3c_wikidata", critical=False, max_retries=1)
async def run(state: RunState) -> dict[str, Any]:
    geo = state.get("geo")
    if not geo or not geo.bbox:
        return {"candidates": [], "source_stats": {"wikidata": {"count": 0, "status": "skipped_no_geo"}}}

    min_lon, min_lat, max_lon, max_lat = geo.bbox

    # SPARQL query for named places within bounding box
    sparql_query = f"""
    SELECT ?item ?itemLabel ?coord ?website ?phone WHERE {{
      SERVICE wikibase:box {{
        ?item wdt:P625 ?coord .
        bd:serviceParam wikibase:cornerSouthWest "Point({min_lon} {min_lat})"^^geo:wktLiteral .
        bd:serviceParam wikibase:cornerNorthEast "Point({max_lon} {max_lat})"^^geo:wktLiteral .
      }}
      OPTIONAL {{ ?item wdt:P856 ?website . }}
      OPTIONAL {{ ?item wdt:P1329 ?phone . }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }} LIMIT 30
    """
    url = "https://query.wikidata.org/sparql"
    headers = {"User-Agent": f"{settings.crawler_user_agent} (contact: {settings.contact_email})", "Accept": "application/json"}

    candidates: list[RawCandidate] = []
    try:
        async with httpx.AsyncClient(timeout=8.0, headers=headers) as client:
            resp = await client.get(url, params={"query": sparql_query, "format": "json"})
            if resp.status_code == 200:
                data = resp.json()
                for b in data.get("results", {}).get("bindings", []):
                    label = b.get("itemLabel", {}).get("value")
                    item_uri = b.get("item", {}).get("value", "")
                    qid = item_uri.split("/")[-1] if "/" in item_uri else item_uri
                    coord_str = b.get("coord", {}).get("value", "")  # e.g. "Point(77.75 12.97)"
                    website = b.get("website", {}).get("value")
                    phone = b.get("phone", {}).get("value")

                    lon, lat = (min_lon + max_lon) / 2, (min_lat + max_lat) / 2
                    if coord_str.startswith("Point(") and ")" in coord_str:
                        coords = coord_str[6:-1].split()
                        if len(coords) == 2:
                            try:
                                lon, lat = float(coords[0]), float(coords[1])
                            except ValueError:
                                pass

                    if label and not label.startswith("Q"):
                        candidates.append(RawCandidate(
                            source="wikidata",
                            source_record_id=qid,
                            name=label,
                            lon=lon,
                            lat=lat,
                            categories=["institution", "entity"],
                            phones=[phone] if phone else [],
                            website=website,
                            raw_properties={"wikidata_id": qid},
                        ))
    except Exception as e:
        logger.warning(f"Wikidata SPARQL query encountered error: {e}")

    return {
        "raw_candidates": candidates,
        "source_stats": {
            "wikidata": {
                "count": len(candidates),
                "status": "completed",
            }
        }
    }
