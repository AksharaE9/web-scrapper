export type RunStatus =
  | "queued"
  | "running"
  | "needs_input"
  | "completed"
  | "partial"
  | "failed"
  | "failed_no_sources"
  | "cancelled";

export type ConfidenceTier = "Verified" | "Likely" | "Unverified";

export interface HealthStatus {
  status: "ok" | "degraded" | "unhealthy";
  neon: { status: "ok" | "error"; error?: string };
  duckdb: { status: "ok" | "error"; error?: string };
  overture: { status: "ok" | "error"; latest_release?: string; error?: string };
  overpass: { status: "ok" | "error"; endpoint?: string; error?: string };
  nominatim: { status: "ok" | "error"; error?: string };
  ollama: { status: "disabled" | "ok" | "error"; model?: string; error?: string };
  disk_cache: { size_mb: number };
}

export interface LocationQuery {
  raw_text?: string;
  locality?: string;
  city?: string;
  state?: string;
  country?: string;
}

export interface QueryInput {
  location: LocationQuery;
  keywords: string[];
  exclude_keywords?: string[];
  max_results?: number;
  min_confidence?: number;
  enrich_websites?: boolean;
  sources?: string[];
}

export interface GeoResolution {
  display_name: string;
  osm_id?: string;
  overture_division_id?: string;
  polygon_wkt: string;
  boundary_kind: "admin_polygon" | "division_polygon" | "buffered_point";
  buffer_m?: number;
  bbox: [number, number, number, number]; // [min_lon, min_lat, max_lon, max_lat]
  centroid: [number, number]; // [lon, lat]
  geo_confidence: number;
  alternatives?: Array<{ display_name: string; osm_id: string; kind: string }>;
}

export interface KeywordPlan {
  keyword: string;
  synonyms: string[];
  overture_basic_categories: string[];
  overture_taxonomy_paths: string[];
  osm_tag_filters: string[];
  name_patterns: string[];
  exclude_patterns: string[];
  plan_confidence: number;
  planner: "taxonomy_rules" | "rag" | "rag+llm";
}

export interface FieldProvenance {
  field: string;
  value: string | null;
  source: string;
  evidence_url?: string;
  evidence_quote?: string;
  extracted_by: "deterministic" | "jsonld" | "llm";
  confidence: number;
  is_selected: boolean;
}

export interface CheckResult {
  check_name: string;
  outcome: "passed" | "failed" | "inconclusive";
  detail: Record<string, any>;
  checked_at: string;
}

export interface Lead {
  id: string;
  canonical_name: string;
  name_norm: string;
  primary_category?: string;
  categories: string[];
  phones_e164: string[];
  emails: string[];
  website_domain?: string;
  website_url?: string;
  socials: Record<string, string>;
  address: Record<string, any>;
  address_text?: string;
  locality?: string;
  city?: string;
  state?: string;
  country: string;
  lon: number;
  lat: number;
  geohash7?: string;
  operating_status?: string;
  confidence: number;
  tier: ConfidenceTier;
  independent_source_count: number;
  source_ids: string[];
  field_provenance?: FieldProvenance[];
  checks?: CheckResult[];
  is_new_business: boolean;
  edge_case: boolean;
  match_score?: number;
  rank?: number;
  distance_km?: number | null;
  distance_m?: number | null;
}

export interface NodeEvent {
  run_id: string;
  node: string;
  status: "queued" | "running" | "completed" | "failed" | "skipped";
  duration_ms?: number;
  count?: number;
  data?: Record<string, any>;
  error?: string;
}

export interface RunSummary {
  id: string;
  created_at: string;
  status: RunStatus;
  locality?: string;
  city?: string;
  state?: string;
  country?: string;
  keywords: string[];
  geo_display_name?: string;
  boundary_kind?: string;
  geo_confidence?: number;
  started_at?: string;
  finished_at?: string;
  error?: string;
  stats?: {
    candidate_count?: number;
    resolved_entity_count?: number;
    metrics?: Record<string, any>;
  };
}

export interface QualityMetrics {
  total_entities: number;
  tier_distribution: {
    Verified: number;
    Likely: number;
    Unverified: number;
  };
  completeness: {
    phone_rate: number;
    email_rate: number;
    website_rate: number;
    address_rate: number;
  };
  capture_recapture?: {
    overture_count: number;
    osm_count: number;
    overlap_count: number;
    estimated_total_population: number;
    estimated_coverage_rate: number;
    caveat: string;
  };
  average_confidence: number;
  multi_source_count: number;
}

export interface KeywordPreset {
  id: string;
  name: string;
  search_categories: string[];
  exclude_keywords: string[];
}
