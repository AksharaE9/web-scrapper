"""
N3a — OvertureAgent

Queries the Overture Maps places theme via DuckDB + anonymous S3.
City-level Parquet cache prevents re-downloading on subsequent runs.

CRITICAL: bbox must be (min_lon, min_lat, max_lon, max_lat).
Schema-drift gate: DESCRIBE at startup; fails loud if required columns missing.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

import duckdb
import structlog

from app.graph.runtime import node
from app.graph.state import GeoResolution, KeywordPlan, RawCandidate, RunState
from app.settings import settings

log = structlog.get_logger()

# Required columns in the Overture places schema (September 2025+)
REQUIRED_COLUMNS = {
    "id", "names", "basic_category", "taxonomy",
    "confidence", "phones", "websites", "emails",
    "socials", "addresses", "brand", "operating_status",
    "sources", "geometry",
}

OVERTURE_S3_BASE = "s3://overturemaps-us-west-2/release"


def _get_duckdb_conn() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute("SET s3_region='us-west-2';")
    con.execute("SET s3_access_key_id='';")     # anonymous
    con.execute("SET s3_secret_access_key='';") # anonymous
    return con


def _discover_latest_release(con: duckdb.DuckDBPyConnection) -> str:
    """
    List the Overture S3 prefix to find the latest release.
    Returns a release string like "2025-07-23.0".
    Falls back to a known recent release if listing fails.
    """
    try:
        # List objects at the base path to find available releases
        result = con.execute(
            f"SELECT * FROM glob('{OVERTURE_S3_BASE}/*/theme=places/type=place/*.parquet') LIMIT 1"
        ).fetchone()
        if result:
            # Extract release from path
            path = str(result[0])
            m = re.search(r"/release/([^/]+)/", path)
            if m:
                return m.group(1)
    except Exception as e:
        log.warning("Overture release discovery failed, using fallback", error=str(e))

    # Fallback to the most recently known release
    return "2025-07-23.0"


def _cache_path(release: str, bbox: tuple[float, float, float, float]) -> Path:
    bbox_hash = hashlib.sha256(f"{release}:{bbox}".encode()).hexdigest()[:16]
    return settings.overture_cache_dir / release / f"{bbox_hash}.parquet"


def _validate_schema(con: duckdb.DuckDBPyConnection, parquet_path: str) -> None:
    """
    Schema-drift gate: assert required columns exist.
    Raises RuntimeError with a clear message if any are missing.
    """
    cols = {row[0] for row in con.execute(
        f"DESCRIBE SELECT * FROM read_parquet('{parquet_path}') LIMIT 0"
    ).fetchall()}
    missing = REQUIRED_COLUMNS - cols
    if missing:
        raise RuntimeError(
            f"Overture schema drift detected! Missing columns: {missing}. "
            "The Overture release schema has changed. Check the Overture changelog "
            "and update REQUIRED_COLUMNS in n3a_overture.py."
        )
    log.info("Overture schema validated", columns_present=len(cols))


def _match_keyword(
    name: str | None,
    categories: list[str],
    plans: list[KeywordPlan],
) -> tuple[float, str]:
    """Return (match_score, match_reason) for the best matching plan."""
    best_score = 0.0
    best_reason = ""

    for plan in plans:
        # Category match (strong)
        for cat in plan.overture_basic_categories + plan.overture_taxonomy_paths:
            if any(cat.lower() in c.lower() for c in categories):
                score = 0.9
                if score > best_score:
                    best_score = score
                    best_reason = f"category:{cat}"

        # Name pattern match (medium)
        if name:
            for pattern in plan.name_patterns:
                if re.search(pattern, name, re.IGNORECASE):
                    score = 0.7
                    if score > best_score:
                        best_score = score
                        best_reason = f"name_pattern:{pattern}"

        # Synonym in name (weak)
        if name:
            for syn in plan.synonyms:
                if syn.lower() in name.lower():
                    score = 0.5
                    if score > best_score:
                        best_score = score
                        best_reason = f"synonym:{syn}"

    return best_score, best_reason


def _extract_candidate(row: dict[str, Any], run_id: str) -> RawCandidate | None:
    """Convert a raw Overture row to a RawCandidate."""
    try:
        # Extract coordinates
        lon = row.get("lon")
        lat = row.get("lat")
        if lon is None or lat is None:
            bbox = row.get("bbox")
            if isinstance(bbox, dict):
                lon = (bbox.get("xmin", 0) + bbox.get("xmax", 0)) / 2.0
                lat = (bbox.get("ymin", 0) + bbox.get("ymax", 0)) / 2.0
            elif isinstance(bbox, (list, tuple)) and len(bbox) == 4:
                lon = (bbox[0] + bbox[2]) / 2.0
                lat = (bbox[1] + bbox[3]) / 2.0

        if lon is None or lat is None or (lon == 0 and lat == 0):
            return None

        # Names
        names = row.get("names") or {}
        name = names.get("primary") if isinstance(names, dict) else str(names)
        if not name:
            return None

        # Categories
        cat_data = row.get("categories") or {}
        tax_data = row.get("taxonomy") or {}
        basic_cat = row.get("basic_category") or ""

        categories: list[str] = []
        if isinstance(cat_data, dict):
            if cat_data.get("primary"):
                categories.append(str(cat_data["primary"]))
            if cat_data.get("alternate"):
                categories.extend(str(x) for x in cat_data["alternate"] if x)
        if isinstance(tax_data, dict):
            if tax_data.get("primary"):
                categories.append(str(tax_data["primary"]))
            if tax_data.get("hierarchy"):
                categories.extend(str(x) for x in tax_data["hierarchy"] if x)
        if basic_cat:
            categories.append(str(basic_cat))

        # Sources and lineage
        sources_raw = row.get("sources") or []
        lineage = list({
            s.get("dataset", "unknown") for s in sources_raw
            if isinstance(s, dict)
        })
        licence_map = {
            s.get("dataset", ""): s.get("license", "unknown")
            for s in sources_raw if isinstance(s, dict)
        }
        primary_licence = licence_map.get(lineage[0], "CDLA-Permissive-2.0") if lineage else "CDLA-Permissive-2.0"

        # Contact info
        phones_raw = row.get("phones") or []
        phones = [p.get("value", "") if isinstance(p, dict) else str(p) for p in phones_raw if p]
        websites_raw = row.get("websites") or []
        websites = [w.get("value", "") if isinstance(w, dict) else str(w) for w in websites_raw if w]
        emails_raw = row.get("emails") or []
        emails = [e.get("value", "") if isinstance(e, dict) else str(e) for e in emails_raw if e]
        socials_raw = row.get("socials") or []
        socials = [s.get("value", "") if isinstance(s, dict) else str(s) for s in socials_raw if s]

        # Address
        addrs_raw = row.get("addresses") or []
        address: dict[str, Any] = {}
        if addrs_raw and isinstance(addrs_raw[0], dict):
            address = addrs_raw[0]

        return RawCandidate(
            source="overture",
            source_record_id=row.get("id", ""),
            source_lineage=lineage,
            name=name,
            lon=float(lon),
            lat=float(lat),
            categories=categories,
            phones=[p for p in phones if p.strip()],
            emails=[e for e in emails if e.strip()],
            websites=[w for w in websites if w.strip()],
            socials=[s for s in socials if s.strip()],
            address=address,
            operating_status=row.get("operating_status"),
            source_confidence=row.get("confidence"),
            licence=primary_licence,
            fetched_at=datetime.now(timezone.utc),
            raw={
                "id": row.get("id"),
                "basic_category": basic_cat,
                "brand": row.get("brand"),
                "sources": sources_raw[:5],  # trim
            },
        )
    except Exception as e:
        log.debug("Failed to parse Overture row", error=str(e))
        return None


import asyncio

def _sync_fetch_overture(geo: GeoResolution, plans: list[KeywordPlan], run_id: str) -> tuple[list[RawCandidate], dict[str, Any]]:
    min_lon, min_lat, max_lon, max_lat = geo.bbox
    con = _get_duckdb_conn()

    try:
        release = _discover_latest_release(con)
        cache_file = _cache_path(release, geo.bbox)

        if cache_file.exists():
            log.info("Overture cache hit", file=str(cache_file))
            parquet_src = str(cache_file)
        else:
            log.info("Overture cache miss, querying S3", release=release)
            s3_path = (
                f"{OVERTURE_S3_BASE}/{release}/theme=places/type=place/*.parquet"
            )
            _validate_schema(con, s3_path)

            cache_file.parent.mkdir(parents=True, exist_ok=True)
            con.execute(f"""
                COPY (
                    SELECT *
                    FROM read_parquet('{s3_path}', hive_partitioning=1)
                    WHERE bbox.xmin >= {min_lon} AND bbox.xmax <= {max_lon}
                      AND bbox.ymin >= {min_lat} AND bbox.ymax <= {max_lat}
                    AND ST_Within(
                        geometry,
                        ST_GeomFromText('{geo.polygon_wkt}')
                    )
                ) TO '{cache_file}' (FORMAT PARQUET)
            """)
            log.info("Overture cache written", file=str(cache_file))
            parquet_src = str(cache_file)

        # Now query from cache
        cur = con.execute(
            f"SELECT *, ST_X(geometry) as lon, ST_Y(geometry) as lat FROM read_parquet('{parquet_src}') "
            "WHERE operating_status != 'permanently_closed' OR operating_status IS NULL"
        )
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]

        candidates = []
        for row in rows:
            c = _extract_candidate(cast(dict[str, Any], row), run_id)
            if c is None:
                continue
            score, reason = _match_keyword(c.name, c.categories, plans)
            if score > 0:
                candidates.append(c)

        log.info("Overture candidates found", count=len(candidates))
        return candidates, {
            "raw_count": len(rows),
            "matched": len(candidates),
            "release": release,
            "cache_hit": cache_file.exists(),
        }

    finally:
        con.close()


@node("n3a_overture", critical=False, max_retries=2)
async def run(state: RunState) -> dict[str, Any]:
    geo = state.get("geo")
    plans: list[KeywordPlan] = state.get("plans", [])

    if not geo:
        return {"errors": [], "source_stats": {"overture": {"error": "no_geo"}}}

    candidates, stats = await asyncio.to_thread(_sync_fetch_overture, geo, plans, state["run_id"])
    return {
        "candidates": candidates,
        "source_stats": {"overture": stats},
    }
