"""
Configuration and Metadata API Router — LeadCore Zero

Exposes graph node definitions, ontology lexicon, sources, ingestion limits,
and scoring thresholds directly to the frontend to ensure zero drift / hardcoding.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, Header, Response, status

router = APIRouter(prefix="/config", tags=["config"])

CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"
LEXICON_DIR = CONFIG_DIR / "lexicon"


def _compute_etag(data: Any) -> str:
    content = json.dumps(data, sort_keys=True, default=str)
    return f'"{hashlib.sha256(content.encode()).hexdigest()[:16]}"'


@router.get("/lexicon")
async def get_lexicon(response: Response, if_none_match: str | None = Header(None)) -> dict[str, Any]:
    """Returns non-evidence terms, honorifics, deity words, and keyword variants."""
    non_evidence_file = LEXICON_DIR / "non_evidence.yaml"
    variants_file = LEXICON_DIR / "variants.yaml"

    non_evidence: dict[str, Any] = {}
    if non_evidence_file.exists():
        non_evidence = yaml.safe_load(non_evidence_file.read_text(encoding="utf-8")) or {}

    variants: dict[str, Any] = {}
    if variants_file.exists():
        variants = yaml.safe_load(variants_file.read_text(encoding="utf-8")) or {}

    # Flatten all non-evidence tokens
    all_non_evidence_terms: list[str] = []
    for terms_list in non_evidence.values():
        if isinstance(terms_list, list):
            all_non_evidence_terms.extend([str(t).lower() for t in terms_list])

    payload = {
        "version": 2,
        "non_evidence_categories": non_evidence,
        "non_evidence_terms": sorted(list(set(all_non_evidence_terms))),
        "variants": variants,
    }

    etag = _compute_etag(payload)
    if if_none_match == etag:
        response.status_code = status.HTTP_304_NOT_MODIFIED
        return {}

    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "public, max-age=300"
    return payload


@router.get("/graph")
async def get_graph_nodes(response: Response, if_none_match: str | None = Header(None)) -> list[dict[str, Any]]:
    """Returns DAG pipeline node metadata."""
    nodes = [
        {"id": "n1_geo", "label": "N1 Geo Resolve", "description": "Resolves boundary polygon and coordinate bbox", "critical": True, "order": 1},
        {"id": "n2_keyword", "label": "N2 Keyword Plan", "description": "Builds ontology taxonomy query filters", "critical": True, "order": 2},
        {"id": "n3a_overture", "label": "N3a Overture Maps", "description": "Fetches places from Overture Parquet release", "critical": False, "order": 3},
        {"id": "n3b_overpass", "label": "N3b OSM Overpass", "description": "Queries live OpenStreetMap POIs", "critical": False, "order": 4},
        {"id": "n4_filter", "label": "N4 Relevance Cascade", "description": "Applies lexical rules and negative veto terms", "critical": True, "order": 5},
        {"id": "n5_resolve", "label": "N5 Entity Resolution", "description": "Deduplicates across sources into golden records", "critical": True, "order": 6},
        {"id": "n6_enrich", "label": "N6 Website Crawl", "description": "Extracts contacts and verifies JSON-LD structured data", "critical": False, "order": 7},
        {"id": "n7_verify", "label": "N7 Verification", "description": "Performs phone and spatial proximity checks", "critical": True, "order": 8},
        {"id": "n8_score", "label": "N8 Confidence Tier", "description": "Assigns Verified, Likely, or Unverified tiers", "critical": True, "order": 9},
        {"id": "n9_critic", "label": "N9 Quality Critic", "description": "Assesses coverage and completeness metrics", "critical": False, "order": 10},
        {"id": "n10_persist", "label": "N10 PostGIS Persist", "description": "Commits records to PostgreSQL database", "critical": True, "order": 11},
        {"id": "n12_report", "label": "N12 Run Reporter", "description": "Summarizes provenance and emits completion status", "critical": True, "order": 12},
    ]

    etag = _compute_etag(nodes)
    if if_none_match == etag:
        response.status_code = status.HTTP_304_NOT_MODIFIED
        return []

    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "public, max-age=600"
    return nodes


@router.get("/sources")
async def get_sources(response: Response, if_none_match: str | None = Header(None)) -> list[dict[str, Any]]:
    """Returns available discovery source connectors with implementation and licence metadata."""
    sources = [
        {
            "id": "overture",
            "label": "Overture Places",
            "enabled": True,
            "implemented": True,
            "status": "ready",
            "licence": "CDLA-Permissive-2.0",
            "note": "Local GeoParquet with automated monthly release discovery and TTL cache.",
        },
        {
            "id": "osm",
            "label": "OpenStreetMap",
            "enabled": True,
            "implemented": True,
            "status": "ready",
            "licence": "ODbL 1.0",
            "note": "Live Overpass API queries with boundary polygon clipping.",
        },
        {
            "id": "wikidata",
            "label": "Wikidata SPARQL",
            "enabled": False,
            "implemented": False,
            "available": False,
            "status": "disabled",
            "licence": "CC0",
            "note": "Knowledge graph business identity entity linking (disabled).",
        },
        {
            "id": "alltheplaces",
            "label": "AllThePlaces",
            "enabled": False,
            "implemented": False,
            "available": False,
            "status": "disabled",
            "licence": "Public Domain",
            "note": "Direct chain store point crawler datasets (disabled).",
        },
        {
            "id": "imports",
            "label": "Custom CSV/GeoJSON",
            "enabled": True,
            "implemented": True,
            "available": True,
            "status": "ready",
            "licence": "Proprietary / User Provided",
            "note": "Local user-uploaded seed files and custom lists.",
        },
    ]

    etag = _compute_etag(sources)
    if if_none_match == etag:
        response.status_code = status.HTTP_304_NOT_MODIFIED
        return []

    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "public, max-age=600"
    return sources


@router.get("/limits")
async def get_limits(response: Response, if_none_match: str | None = Header(None)) -> dict[str, Any]:
    """Returns dynamic limits for query and scrape executions."""
    limits = {
        "max_results_min": 1,
        "max_results_max": 5000,
        "default": 100,
        "warn_above": 1000,
        "default_cache_age_days": 30,
        "max_cache_age_days": 365,
    }

    etag = _compute_etag(limits)
    if if_none_match == etag:
        response.status_code = status.HTTP_304_NOT_MODIFIED
        return {}

    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "public, max-age=600"
    return limits


@router.get("/thresholds")
async def get_thresholds(response: Response, if_none_match: str | None = Header(None)) -> dict[str, Any]:
    """Returns classification thresholds and scoring tiers."""
    scoring_file = CONFIG_DIR / "scoring.yaml"
    scoring: dict[str, Any] = {}
    if scoring_file.exists():
        scoring = yaml.safe_load(scoring_file.read_text(encoding="utf-8")) or {}

    thresholds = {
        "tau_hi": scoring.get("tau_hi", 0.75),
        "tau_lo": scoring.get("tau_lo", 0.35),
        "tiers": ["Verified", "Likely", "Unverified"],
        "review_band": [scoring.get("tau_lo", 0.35), scoring.get("tau_hi", 0.75)],
    }

    etag = _compute_etag(thresholds)
    if if_none_match == etag:
        response.status_code = status.HTTP_304_NOT_MODIFIED
        return {}

    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "public, max-age=600"
    return thresholds


@router.get("/geo")
async def get_geo_config(response: Response, if_none_match: str | None = Header(None)) -> dict[str, Any]:
    """Returns dynamic geographic resolution parameters and buffer thresholds."""
    geo_file = CONFIG_DIR / "geo.yaml"
    geo_config: dict[str, Any] = {}
    if geo_file.exists():
        geo_config = yaml.safe_load(geo_file.read_text(encoding="utf-8")) or {}

    etag = _compute_etag(geo_config)
    if if_none_match == etag:
        response.status_code = status.HTTP_304_NOT_MODIFIED
        return {}

    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "public, max-age=600"
    return geo_config

