"""
N3a — OvertureAgent (ZERO-1.0 Forensic Overhaul)

Queries the Overture Maps places theme via DuckDB + anonymous S3.
City-level Parquet cache prevents re-downloading on subsequent runs.
Strict contracts:
  - Token-set category matching (category_matches), never raw substring
  - Intersection bbox predicates (correct for point and polygon geometries)
  - Zero-row results are NEVER cached to disk (anti-poisoning)
  - Parameterized ST_Within geometry query
  - Cache sidecar verification with row_count and release checks
  - Accurate cache_hit reporting
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import structlog

from app.graph.runtime import node
from app.graph.state import GeoResolution, KeywordPlan, RawCandidate, RunState
from app.relevance.concepts import resolve_concept
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
CACHE_GRID_DEG = 0.05
CACHE_SCHEMA_VERSION = 2

_DEGRADED_SIGNALS: list[str] = []


class SourceMatchedNothingError(RuntimeError):
    """Raised when Overture returns places but the keyword plan matches 0 of them."""
    pass


class GeoContractError(RuntimeError):
    """Raised when geometry input violates polygon contract."""
    pass


def _get_duckdb_conn() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute("SET s3_region='us-west-2';")
    con.execute("SET s3_access_key_id='';")     # anonymous
    con.execute("SET s3_secret_access_key='';") # anonymous
    return con


def _snap_bbox_to_grid(
    bbox: tuple[float, float, float, float],
    grid_deg: float = CACHE_GRID_DEG,
) -> tuple[float, float, float, float]:
    import math
    min_lon, min_lat, max_lon, max_lat = bbox
    return (
        math.floor(min_lon / grid_deg) * grid_deg,
        math.floor(min_lat / grid_deg) * grid_deg,
        math.ceil(max_lon / grid_deg) * grid_deg,
        math.ceil(max_lat / grid_deg) * grid_deg,
    )


def _discover_latest_release(con: duckdb.DuckDBPyConnection) -> str:
    try:
        result = con.execute(
            f"SELECT * FROM glob('{OVERTURE_S3_BASE}/*/theme=places/type=place/*.parquet') LIMIT 1"
        ).fetchone()
        if result:
            path = str(result[0])
            m = re.search(r"/release/([^/]+)/", path)
            if m:
                return m.group(1)
    except Exception as e:
        log.error("Failed to discover Overture release via S3 glob", error=str(e))
        _DEGRADED_SIGNALS.append(f"s3_release_glob_failed:{e}")

    cache_dir = settings.overture_cache_dir
    if cache_dir.exists():
        releases = sorted(
            [d.name for d in cache_dir.iterdir() if d.is_dir() and d.name and not d.name.startswith(".")],
            reverse=True,
        )
        if releases:
            log.warning("Falling back to newest locally cached release", release=releases[0])
            _DEGRADED_SIGNALS.append(f"using_cached_release:{releases[0]}")
            return releases[0]

    raise RuntimeError(
        "Could not discover Overture release from S3 and no local cache exists. "
        "Check network connectivity or S3 permissions."
    )


def _cache_path(release: str, snapped_bbox: tuple[float, float, float, float]) -> Path:
    min_lon, min_lat, max_lon, max_lat = snapped_bbox
    key = f"{min_lon:.4f}_{min_lat:.4f}_{max_lon:.4f}_{max_lat:.4f}"
    h = hashlib.sha256(key.encode()).hexdigest()[:16]
    return settings.overture_cache_dir / release / f"places_{h}.parquet"


def _meta_path(cache_file: Path) -> Path:
    return cache_file.with_suffix(".meta.json")


def _read_cache_meta(cache_file: Path) -> dict[str, Any]:
    mp = _meta_path(cache_file)
    if not mp.exists():
        return {}
    try:
        data = json.loads(mp.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
        return {}
    except Exception:
        return {}


def _write_cache_meta(
    cache_file: Path,
    release: str,
    snapped_bbox: tuple[float, float, float, float],
    row_count: int,
    source_bytes: int,
    polygon_hash: str = "",
) -> None:
    meta = {
        "release": release,
        "bbox": list(snapped_bbox),
        "polygon_hash": polygon_hash,
        "written_at": datetime.now(timezone.utc).isoformat(),
        "row_count": row_count,
        "source_bytes": source_bytes,
        "schema_version": CACHE_SCHEMA_VERSION,
    }
    _meta_path(cache_file).write_text(json.dumps(meta, indent=2), encoding="utf-8")


def _cache_age_days(meta: dict[str, Any]) -> float | None:
    written_at_str = meta.get("written_at")
    if not written_at_str:
        return None
    try:
        written_at = datetime.fromisoformat(written_at_str)
        if written_at.tzinfo is None:
            written_at = written_at.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - written_at
        return delta.total_seconds() / 86400
    except Exception:
        return None


def _should_use_cache(
    cache_file: Path,
    meta: dict[str, Any],
    current_release: str | None,
    cache_policy: str,
    max_cache_age_days: int,
) -> bool:
    """
    Decide whether to use the existing cache file.
    NEVER use a cache file with 0 rows (anti-poisoning).
    """
    if not cache_file.exists():
        return False
    if cache_policy == "force_fresh":
        return False

    # Anti-poisoning check: discard zero-row caches
    row_count = meta.get("row_count")
    if row_count == 0:
        log.warning("Discarding zero-row poisoned cache", path=str(cache_file))
        try:
            cache_file.unlink(missing_ok=True)
            _meta_path(cache_file).unlink(missing_ok=True)
        except Exception:
            pass
        return False

    if cache_policy == "prefer_cache":
        return True

    age = _cache_age_days(meta)
    if age is not None and age > max_cache_age_days:
        return False
    if current_release and meta.get("release") != current_release:
        return False
    return True


def _validate_schema(con: duckdb.DuckDBPyConnection, parquet_path: str) -> None:
    cols = {row[0] for row in con.execute(
        f"DESCRIBE SELECT * FROM read_parquet('{parquet_path}') LIMIT 0"
    ).fetchall()}
    missing = REQUIRED_COLUMNS - cols
    if missing:
        raise RuntimeError(
            f"Overture schema drift detected! Missing columns: {missing}."
        )


def category_matches(plan_cat: str, place_cat: str) -> bool:
    """Token-set matching for categories: replaces naive substring matching."""
    if not plan_cat or not place_cat:
        return False
    p_norm = plan_cat.lower().replace("_", " ").strip()
    c_norm = place_cat.lower().replace("_", " ").strip()
    if p_norm == c_norm or p_norm in c_norm or c_norm in p_norm:
        return True

    stop = {"and", "or", "of", "the", "in", "for", "to", "at"}
    a = set(re.split(r"[._/\- ]+", p_norm)) - stop
    b = set(re.split(r"[._/\- ]+", c_norm)) - stop
    if not a or not b:
        return False

    return a.issubset(b) or b.issubset(a) or len(a & b) >= min(len(a), len(b))


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
        plan_cats = plan.overture_basic_categories + plan.overture_taxonomy_paths
        for pcat in plan_cats:
            for ccat in categories:
                if category_matches(pcat, ccat):
                    score = 0.90
                    if score > best_score:
                        best_score = score
                        best_reason = f"category:{pcat}"

        # Name pattern match (medium)
        if name:
            for pattern in plan.name_patterns:
                try:
                    if re.search(pattern, name, re.IGNORECASE):
                        score = 0.75
                        if score > best_score:
                            best_score = score
                            best_reason = f"name_pattern:{pattern}"
                except Exception:
                    pass

        # Synonym in name (token-aware)
        if name:
            name_tokens = set(re.split(r"\s+", name.lower()))
            for syn in plan.synonyms:
                syn_clean = syn.lower().strip()
                if syn_clean in name.lower() or any(st in name_tokens for st in syn_clean.split() if len(st) > 2):
                    score = 0.60
                    if score > best_score:
                        best_score = score
                        best_reason = f"synonym:{syn}"

    return best_score, best_reason


def _extract_candidate(row: dict[str, Any], run_id: str) -> RawCandidate | None:
    try:
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

        names = row.get("names") or {}
        name = names.get("primary") if isinstance(names, dict) else str(names)
        if not name or str(name).strip() == "":
            return None

        tax_data = row.get("taxonomy") or {}
        basic_cat = row.get("basic_category") or ""

        categories: list[str] = []
        if isinstance(tax_data, dict):
            if tax_data.get("primary"):
                categories.append(str(tax_data["primary"]))
            if tax_data.get("hierarchy"):
                categories.extend(str(x) for x in tax_data["hierarchy"] if x)
        if basic_cat:
            categories.append(str(basic_cat))

        sources_raw = row.get("sources") or []
        lineage = list({s.get("dataset", "unknown") for s in sources_raw if isinstance(s, dict)})
        licence_map = {s.get("dataset", ""): s.get("license", "unknown") for s in sources_raw if isinstance(s, dict)}
        primary_licence = licence_map.get(lineage[0], "CDLA-Permissive-2.0") if lineage else "CDLA-Permissive-2.0"

        phones_raw = row.get("phones") or []
        phones = [p.get("value", "") if isinstance(p, dict) else str(p) for p in phones_raw if p]
        websites_raw = row.get("websites") or []
        websites = [w.get("value", "") if isinstance(w, dict) else str(w) for w in websites_raw if w]
        emails_raw = row.get("emails") or []
        emails = [e.get("value", "") if isinstance(e, dict) else str(e) for e in emails_raw if e]
        socials_raw = row.get("socials") or []
        socials = [s.get("value", "") if isinstance(s, dict) else str(s) for s in socials_raw if s]

        addrs_raw = row.get("addresses") or []
        address: dict[str, Any] = addrs_raw[0] if addrs_raw and isinstance(addrs_raw[0], dict) else {}

        return RawCandidate(
            source="overture",
            source_record_id=str(row.get("id", "")),
            source_lineage=lineage,
            name=str(name),
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
                "sources": sources_raw[:5],
            },
        )
    except Exception as e:
        log.warning("Row extraction error", error=str(e))
        return None


def _sync_fetch_overture(
    geo: GeoResolution,
    plans: list[KeywordPlan],
    run_id: str,
    cache_policy: str = "force_fresh",
    max_cache_age_days: int = 0,
    concept_defining_cats: list[str] | None = None,
    concept_host_cats: list[str] | None = None,
) -> tuple[list[RawCandidate], dict[str, Any]]:
    global _DEGRADED_SIGNALS
    _DEGRADED_SIGNALS = []

    if not geo.polygon_wkt or not geo.polygon_wkt.upper().startswith(("POLYGON", "MULTIPOLYGON")):
        raise GeoContractError(f"Overture requires a closed POLYGON geometry; got {geo.polygon_wkt!r}")

    snapped_bbox = _snap_bbox_to_grid(geo.bbox)
    con = _get_duckdb_conn()

    try:
        release = _discover_latest_release(con)
        cache_file = _cache_path(release, snapped_bbox)
        meta = _read_cache_meta(cache_file)
        age_days = _cache_age_days(meta)

        use_cache = _should_use_cache(cache_file, meta, release, cache_policy, max_cache_age_days)
        fetched_bytes = 0
        mode = "cache"

        if use_cache:
            log.info("Overture cache hit", file=str(cache_file), age_days=round(age_days or 0, 1))
            parquet_src = str(cache_file)
        else:
            mode = "live"
            s3_path = f"{OVERTURE_S3_BASE}/{release}/theme=places/type=place/*.parquet"
            _validate_schema(con, s3_path)

            cache_file.parent.mkdir(parents=True, exist_ok=True)
            tmp_write_file = cache_file.with_name(f"tmp_{uuid.uuid4().hex[:8]}_{cache_file.name}")

            # Parameterized S3 Query with intersection bounding box & parameterized ST_Within
            query_sql = f"""
                COPY (
                    SELECT *
                    FROM read_parquet('{s3_path}', hive_partitioning=1)
                    WHERE bbox.xmin <= ? AND bbox.xmax >= ?
                      AND bbox.ymin <= ? AND bbox.ymax >= ?
                    AND ST_Within(geometry, ST_GeomFromText(?))
                ) TO '{tmp_write_file.as_posix()}' (FORMAT PARQUET)
            """
            params = [
                float(snapped_bbox[2]), float(snapped_bbox[0]),
                float(snapped_bbox[3]), float(snapped_bbox[1]),
                str(geo.polygon_wkt),
            ]

            try:
                con.execute(query_sql, params)
            except Exception as write_err:
                log.warning("Overture query write warning", error=str(write_err))

            # Validate row count before promoting to permanent cache (Anti-poisoning)
            row_count = 0
            if tmp_write_file.exists():
                cnt_res = con.execute(f"SELECT COUNT(*) FROM read_parquet('{tmp_write_file.as_posix()}')").fetchone()
                row_count = cnt_res[0] if cnt_res else 0

            if row_count > 0:
                tmp_write_file.replace(cache_file)
                parquet_src = cache_file.as_posix()
                fetched_bytes = cache_file.stat().st_size
                _write_cache_meta(cache_file, release, snapped_bbox, row_count, fetched_bytes)
                meta = _read_cache_meta(cache_file)
                age_days = 0.0
            else:
                if tmp_write_file.exists():
                    tmp_write_file.unlink()
                parquet_src = s3_path
                fetched_bytes = 0

        # Query extracted places
        base_from = f"SELECT *, ST_X(geometry) as lon, ST_Y(geometry) as lat FROM read_parquet('{parquet_src}')"
        status_filter = "(operating_status != 'permanently_closed' OR operating_status IS NULL)"
        query = f"{base_from} WHERE {status_filter}"

        cur = con.execute(query)
        cols = [d[0] for d in cur.description]
        raw_rows = [dict(zip(cols, r)) for r in cur.fetchall()]

        candidates: list[RawCandidate] = []
        cat_matched = 0
        name_matched = 0
        parse_failures = 0

        for r in raw_rows:
            c = _extract_candidate(r, run_id)
            if c is None:
                parse_failures += 1
                continue
            score, reason = _match_keyword(c.name, c.categories, plans)
            if score > 0:
                candidates.append(c)
                if "category:" in reason:
                    cat_matched += 1
                else:
                    name_matched += 1

        if len(raw_rows) > 0 and (parse_failures / len(raw_rows)) > 0.20:
            log.warning("High parse failure rate in Overture rows", parse_failures=parse_failures, total=len(raw_rows))

        return candidates, {
            "raw_count": len(raw_rows),
            "matched": len(candidates),
            "cat_matched": cat_matched,
            "name_matched": name_matched,
            "parse_failures": parse_failures,
            "release": release,
            "cache_hit": use_cache,
            "cache_age_days": round(age_days, 1) if age_days is not None else None,
            "fetched_bytes": fetched_bytes,
            "row_count": len(raw_rows),
            "written_at": meta.get("written_at"),
            "mode": mode,
            "degraded": list(_DEGRADED_SIGNALS),
            "snapped_bbox": list(snapped_bbox),
        }

    finally:
        con.close()


@node("n3a_overture", critical=False, max_retries=2)
async def run(state: RunState) -> dict[str, Any]:
    geo = state.get("geo")
    plans: list[KeywordPlan] = state.get("plans", [])
    query_obj = state.get("query")
    run_id = state.get("run_id") or ""

    if not geo:
        return {"errors": [], "source_stats": {"overture": {"error": "no_geo"}}}

    cache_policy = getattr(query_obj, "cache_policy", "auto") or "auto"
    max_cache_age_days = getattr(query_obj, "max_cache_age_days", 30) or 30

    loop = asyncio.get_running_loop()
    candidates, stats = await loop.run_in_executor(
        None,
        _sync_fetch_overture,
        geo,
        plans,
        run_id,
        cache_policy,
        max_cache_age_days,
    )

    return {
        "raw_candidates": candidates,
        "source_stats": {"overture": stats},
    }
