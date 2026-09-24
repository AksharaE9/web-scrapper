"""
LangGraph State Schema — LeadCore Zero v2

Single source of truth for the RunState TypedDict and all Pydantic models.
Reducers ensure parallel source branches can safely write to shared keys.

COORDINATE CONVENTION: All lon/lat in GeoJSON order (longitude first, latitude second).
The unit test test_geo.py::test_koramangala_centroid enforces this.
"""

from __future__ import annotations

import operator
from datetime import datetime, timezone
from typing import Annotated, Any, Literal, TypedDict

from pydantic import BaseModel, Field, field_validator


# ── Reducer helpers ───────────────────────────────────────────────────────────

def merge_dicts(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """Reducer: merge two dicts, summing integer values."""
    result = dict(a)
    for k, v in b.items():
        if k in result and isinstance(result[k], int) and isinstance(v, int):
            result[k] += v
        else:
            result[k] = v
    return result


# ── Input models ──────────────────────────────────────────────────────────────

class LocationInput(BaseModel):
    raw_text: str | None = None       # "gyms in Koramangala, Karnataka, India"
    locality: str | None = None       # "Koramangala"
    city: str | None = None           # "Bengaluru"
    state: str | None = None          # "Karnataka"
    country: str = "India"
    lat: float | None = None          # Direct centroid coordinate
    lon: float | None = None          # Direct centroid coordinate (GeoJSON lon first)
    radius_m: float | None = None     # Search radius in metres


class QueryInput(BaseModel):
    location: LocationInput
    keywords: list[str] = Field(..., min_length=1)
    exclude_keywords: list[str] = []
    max_results: int = Field(default=500, ge=1, le=5000)
    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    enrich_websites: bool = True
    sources: set[Literal["overture", "osm", "wikidata", "alltheplaces", "imports", "overpass"]] = {
        "overture", "osm"
    }
    # Cache policy for Overture data (defaults to force_fresh for live fresh data every run)
    cache_policy: Literal["force_fresh", "auto", "prefer_cache"] = "force_fresh"
    max_cache_age_days: int = Field(default=0, ge=0, le=365)


# ── Budget ────────────────────────────────────────────────────────────────────

class NodeBudget(BaseModel):
    max_http_calls: int = 50
    max_llm_calls: int = 10
    max_wall_seconds: int = 300


class Budget(BaseModel):
    max_http_calls: int = 500
    max_llm_calls: int = 50
    max_wall_seconds: int = 1800   # 30 minutes total run budget
    per_node: dict[str, NodeBudget] = {}
    http_calls_used: int = 0
    llm_calls_used: int = 0
    started_at: datetime | None = None


# ── Geo resolution ────────────────────────────────────────────────────────────

BoundaryKind = Literal["admin_polygon", "division_polygon", "buffered_point"]
BoundarySource = Literal[
    "osm_relation",
    "osm_way",
    "overture_division_area",
    "poi_concave_hull",
    "h3_cover",
    "nominatim_bbox",
    "radius_circle",
]


class GeoResolution(BaseModel):
    display_name: str
    osm_id: str | None = None
    overture_division_id: str | None = None
    polygon_wkt: str                   # WKT of the boundary polygon used
    boundary_geojson: dict[str, Any] | None = None  # GeoJSON representation of polygon_wkt
    boundary_kind: BoundaryKind = "admin_polygon"
    boundary_source: BoundarySource = "radius_circle"
    buffer_m: int | None = None
    # ALWAYS (min_lon, min_lat, max_lon, max_lat) — never swapped
    bbox: tuple[float, float, float, float] = Field(...)
    # ALWAYS (lon, lat) — GeoJSON convention
    centroid: tuple[float, float] = Field(...)
    geo_confidence: float = Field(ge=0.0, le=1.0)
    alternatives: list[dict[str, Any]] = []

    @field_validator("bbox")
    @classmethod
    def _validate_bbox(cls, v: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
        min_lon, min_lat, max_lon, max_lat = v
        assert min_lon < max_lon, f"bbox lon range invalid: {min_lon} >= {max_lon}"
        assert min_lat < max_lat, f"bbox lat range invalid: {min_lat} >= {max_lat}"
        # Guard against swapped lat/lon: India is roughly lat 8-37, lon 68-97
        assert -180 <= min_lon <= 180, f"min_lon out of range: {min_lon}"
        assert -90 <= min_lat <= 90, f"min_lat out of range: {min_lat}"
        return v

    @field_validator("centroid")
    @classmethod
    def _validate_centroid(cls, v: tuple[float, float]) -> tuple[float, float]:
        lon, lat = v
        assert -180 <= lon <= 180, f"centroid lon out of range: {lon}"
        assert -90 <= lat <= 90, f"centroid lat out of range: {lat}"
        return v


# ── Keyword plan ──────────────────────────────────────────────────────────────

class KeywordPlan(BaseModel):
    keyword: str
    synonyms: list[str] = []
    overture_basic_categories: list[str] = []
    overture_taxonomy_paths: list[str] = []
    osm_tag_filters: list[str] = []    # e.g. ["leisure=fitness_centre", "amenity=gym"]
    name_patterns: list[str] = []     # regex, case-insensitive
    exclude_patterns: list[str] = []
    plan_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    planner: Literal["taxonomy_rules", "rag", "rag+llm"] = "taxonomy_rules"


# ── Raw candidates ────────────────────────────────────────────────────────────

class RawCandidate(BaseModel):
    source: str                        # overture|osm|wikidata|alltheplaces|import:filename
    source_record_id: str
    source_lineage: list[str] = []    # e.g. ["meta", "foursquare"] from Overture sources[]
    name: str
    lon: float                         # GeoJSON convention: longitude first
    lat: float
    categories: list[str] = []
    phones: list[str] = []
    emails: list[str] = []
    websites: list[str] = []
    socials: list[str] = []
    address: dict[str, Any] = {}
    operating_status: str | None = None
    source_confidence: float | None = None
    licence: str = "unknown"
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    raw: dict[str, Any] = {}          # trimmed to useful keys; no full HTML

    # ── Derived fields for entity resolution blocking ─────────────────────────
    # These are computed from the fields above and used by splink_model.py.
    geohash7: str | None = None        # 7-char geohash for geo-blocking
    phones_e164: list[str] = []        # normalized E.164 phones for phone-blocking
    website_domain: str | None = None  # registrable domain for domain-blocking

    # ── Location fields derived from address dict ─────────────────────────────
    locality: str | None = None
    city: str | None = None
    state: str | None = None
    country: str = "India"

    def model_post_init(self, __context: Any) -> None:
        """Derive blocking keys and location fields from raw fields after validation."""
        import re
        # geohash7 from lat/lon
        if self.geohash7 is None and self.lat and self.lon:
            try:
                import pygeohash
                object.__setattr__(self, "geohash7", pygeohash.encode(self.lat, self.lon, precision=7))
            except Exception:
                pass
        # phones_e164: keep entries that look like E.164 (+digits), else pass through
        if not self.phones_e164 and self.phones:
            normalized = []
            for p in self.phones:
                cleaned = re.sub(r"[^\d+]", "", p)
                if cleaned:
                    normalized.append(cleaned)
            object.__setattr__(self, "phones_e164", normalized)
        # website_domain: extract registrable domain from first website
        if self.website_domain is None and self.websites:
            try:
                from urllib.parse import urlparse
                parsed = urlparse(self.websites[0] if "://" in self.websites[0] else "https://" + self.websites[0])
                host = parsed.netloc or parsed.path.split("/")[0]
                # Strip www. prefix
                host = re.sub(r"^www\.", "", host.lower())
                if host:
                    object.__setattr__(self, "website_domain", host)
            except Exception:
                pass
        # locality/city/state/country: derive from address dict if not already set
        if isinstance(self.address, dict):
            if self.locality is None:
                val = self.address.get("locality") or self.address.get("suburb") or self.address.get("neighbourhood")
                if val:
                    object.__setattr__(self, "locality", str(val))
            if self.city is None:
                val = self.address.get("city") or self.address.get("town") or self.address.get("village")
                if val:
                    object.__setattr__(self, "city", str(val))
            if self.state is None:
                val = self.address.get("state") or self.address.get("region")
                if val:
                    object.__setattr__(self, "state", str(val))
            # country: keep default "India" unless address says otherwise
            raw_country = self.address.get("country")
            if raw_country and self.country == "India":
                object.__setattr__(self, "country", str(raw_country))




# ── Verification check ────────────────────────────────────────────────────────

class CheckResult(BaseModel):
    check_name: str
    outcome: Literal["passed", "failed", "inconclusive"]
    detail: dict[str, Any] = {}
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Resolved entity (golden record) ──────────────────────────────────────────

class FieldProvenance(BaseModel):
    field: str
    value: str | None
    source: str
    evidence_url: str | None = None
    evidence_quote: str | None = None
    extracted_by: Literal["deterministic", "jsonld", "llm"] = "deterministic"
    confidence: float = 0.5
    is_selected: bool = False


class ResolvedEntity(BaseModel):
    id: str                            # UUID string
    canonical_name: str
    name_norm: str
    primary_category: str | None = None
    categories: list[str] = []
    phones_e164: list[str] = []
    emails: list[str] = []
    website_domain: str | None = None
    website_url: str | None = None
    socials: dict[str, str] = {}
    address: dict[str, Any] = {}
    address_text: str | None = None
    locality: str | None = None
    city: str | None = None
    state: str | None = None
    country: str = "India"
    lon: float                         # GeoJSON convention
    lat: float
    geohash7: str | None = None
    operating_status: str | None = None
    confidence: float = 0.0
    tier: str = "Unverified"          # Verified|Likely|Unverified
    independent_source_count: int = 0
    source_ids: list[str] = []        # [f"{source}:{source_record_id}"]
    field_provenance: list[FieldProvenance] = []
    checks: list[CheckResult] = []
    is_new_business: bool = True
    edge_case: bool = False
    distance_m: float | None = None
    distance_km: float | None = None
    relevance_decision: dict[str, Any] = Field(default_factory=dict)


# ── Node error ────────────────────────────────────────────────────────────────

class NodeError(BaseModel):
    node: str
    error: str
    traceback: str | None = None
    is_critical: bool = False
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Run state ─────────────────────────────────────────────────────────────────

class RunState(TypedDict, total=False):
    run_id: str
    query: QueryInput

    # Filled by N1 and N2 in parallel
    geo: GeoResolution | None
    plans: list[KeywordPlan]

    # Fan-in from parallel source nodes (reducer: extend)
    raw_candidates: Annotated[list[RawCandidate], operator.add]
    candidates: list[RawCandidate]
    source_stats: Annotated[dict[str, dict[str, Any]], merge_dicts]

    # Resolution and enrichment
    entities: list[ResolvedEntity]
    verifications: dict[str, list[CheckResult]]

    # Quality critic loop counter
    iteration: int

    # Budget tracking
    budget: Budget

    # Error log (reducer: extend)
    errors: Annotated[list[NodeError], operator.add]

    # Degradation signals (reducer: extend) — non-empty means the run used fallback data
    # Each entry is a string reason code, e.g. "overture_release_discovery_failed"
    degraded: Annotated[list[str], operator.add]

    # Metrics and reporting
    metrics: dict[str, Any]

    # Expansion ladder telemetry — list of per-rung stats dicts from N4
    # Each entry: {rung, strategy, candidates_evaluated, accepted, review, rejected, elapsed_ms}
    expansion_stats: list[dict[str, Any]]

    # Human-in-the-loop disambiguation
    disambiguation_choice: str | None
