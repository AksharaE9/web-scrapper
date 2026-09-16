# LeadCore Zero v2 — Architectural Decisions Log

This document records all significant decisions made during the design of v2,
with rationale. Once a decision is recorded here, it is not re-litigated without
new evidence.

---

## D-001 — Data Source Strategy

**Decision date:** 2026-09-16  
**Status:** Accepted

### Included Sources

| Source | Rationale |
|---|---|
| Overture Maps `places` theme | ~64M+ POIs; public S3, anonymous DuckDB query; CDLA-Permissive-2.0 |
| Overture Maps `divisions` theme | Authoritative locality/neighbourhood polygons; same access |
| OSM via Overpass API | Independent verification; public, no key; ODbL |
| Nominatim + Photon | Geocoding; public; max 1 req/s cached |
| Business websites (Scrapling) | Email, phone, JSON-LD enrichment; robots.txt obeyed |
| Wikidata SPARQL | Institutions (colleges, hospitals); CC0; public endpoint |
| AllThePlaces | Brand/chain locations; public GeoJSON outputs |
| User CSV imports | Any legitimately-downloaded open dataset |

### Excluded Sources (with reasons)

| Source | Reason for Exclusion |
|---|---|
| Google Maps DOM scraping | Explicitly prohibited by Google Terms of Service §5.3 |
| Google Places API | Requires API key (violates ₹0 / no-key constraint) |
| Foursquare Places Portal | Now requires a portal token; data already in Overture |
| Justdial | Terms of Service prohibit scraping |
| IndiaMART | Terms of Service prohibit scraping |
| Sulekha | Terms of Service prohibit scraping |
| LinkedIn | Terms of Service prohibit scraping; repeated legal enforcement |
| Search-engine result scraping | Terms of Service + structural instability; anti-scraping measures |
| SMTP mailbox probing | Gets IPs blocklisted; abusive practice; MX-only approach used instead |

---

## D-002 — Tool Selection

**Decision date:** 2026-09-16  
**Status:** Accepted

### Accepted Tools

| Tool | Role |
|---|---|
| Scrapling (v0.4.x) | All website fetching and crawling — the single crawling framework |
| DuckDB (`spatial`, `httpfs`) | Overture GeoParquet queries; Splink backend |
| Splink | Probabilistic entity resolution (Fellegi–Sunter, EM-trained) |
| LangGraph + Postgres checkpointer | Agent orchestration, fan-out, resumability |
| fastembed (`BAAI/bge-small-en-v1.5`, 384-d) | ONNX CPU embeddings |
| Ollama (optional) | Local LLM for keyword planning + grounded extraction |
| psycopg 3 async + psycopg_pool | Neon Postgres async access |
| Alembic | Database migrations |
| phonenumbers | Phone normalisation to E.164 |
| email-validator | Email syntax validation |
| dnspython | MX record lookups |
| rapidfuzz | Fuzzy string matching (entity resolution features, alias resolution) |
| extruct | JSON-LD / microdata extraction from HTML |
| shapely | Geometric operations (point-in-polygon, buffering) |
| pygeohash | Geohash-7 blocking for entity resolution |
| tenacity | Retry policies with exponential backoff + jitter |
| httpx | HTTP client (Nominatim, Overpass, Wikidata, Ollama, health checks) |

### Rejected Tools

| Tool | Reason |
|---|---|
| Crawl4AI | Overlaps Scrapling markdown + crawling; one framework only |
| ScrapeGraphAI | We implement grounded extraction with stricter evidence rules |
| Firecrawl | Cloud requires key; self-hosting adds Redis + Playwright for no gain |
| Scrapy | Scrapling's Spider API covers the same pattern |
| Crawlee | Overlap with Scrapling |
| Browser Use | LLM-driven browsing is slow and nondeterministic with a 7B model |
| Katana | Security-recon crawler; Scrapling link extraction + sitemaps sufficient |
| Celery / Redis | Bounded asyncio worker + LangGraph checkpoints sufficient; fewer parts |
| Playwright (direct) | Used only as a transitive dep via Scrapling's DynamicFetcher |

### Deferred (not in v1, adapter interface provided)

| Tool | Condition for introduction |
|---|---|
| Crawl4AI | If profiler shows Scrapling is a bottleneck and Crawl4AI offers >20% gain |
| Rust via PyO3/maturin | Only if Phase 7 profiler shows a Python hot loop consuming >30% wall time |

---

## D-003 — LLM Strategy

**Decision date:** 2026-09-16  
**Status:** Accepted

The LLM is **optional at runtime** (`LLM_ENABLED=false` is the safe default).
Every node that uses the LLM must have a deterministic fallback.

| Use | LLM role | Fallback |
|---|---|---|
| Keyword planning (N2) | Refine category/tag selections from retrieved taxonomy list | Use top-k RAG results directly |
| Grounded extraction (N6) | Extract contact fields with `evidence_chunk_id` + `evidence_quote` | Deterministic extractors (JSON-LD, regex) only |
| Input parsing (N0) | Parse `raw_text` into structured location + keywords | Regex + comma/semicolon split |

**Grounded extraction contract (non-negotiable):**
- The LLM is given only retrieved chunks, not the full page.
- Output must include `evidence_chunk_id` (the chunk's DB id) and
  `evidence_quote` (verbatim substring from that chunk).
- Post-validation: the quote must literally appear in the chunk text AND
  the extracted value must literally appear in the quote.
- Failure of post-validation → field is discarded silently.
- No evidence → no field. The LLM may never invent a value.

LLM calls use `temperature=0` and are cached by `(model, prompt_hash)`.

---

## D-004 — Neon Connection Architecture

**Decision date:** 2026-09-16  
**Status:** Accepted

Neon in transaction-mode pooling (PgBouncer) does not support server-side
prepared statements. Two separate connection strings are used:

| Variable | URL type | Used by | Notes |
|---|---|---|---|
| `DATABASE_URL` | Pooled (`-pooler` host) | API pool (`psycopg_pool.AsyncConnectionPool`) | `prepare_threshold=None` mandatory |
| `DATABASE_URL_DIRECT` | Direct (non-pooled) | Alembic migrations; LangGraph PostgresSaver | Full SQL feature set |

No background Neon polling. SSE is served from an in-memory event bus.
Bulk writes use `COPY` into a staging table, not row-by-row inserts.

---

## D-005 — Coordinate Order Convention

**Decision date:** 2026-09-16  
**Status:** Accepted, enforced by tests

All coordinates in this codebase follow **GeoJSON / PostGIS convention:**
**(longitude, latitude)** — not (lat, lon).

Specific rules:
- `GeoResolution.bbox` = `(min_lon, min_lat, max_lon, max_lat)`
- `GeoResolution.centroid` = `(lon, lat)`
- `RawCandidate.lon`, `RawCandidate.lat` — separate named fields, never a tuple
- PostGIS: `ST_SetSRID(ST_Point(lon, lat), 4326)` — lon first always
- DuckDB Overture: `ST_AsText(geometry)` returns WKT in lon/lat order;
  `GeoResolution.bbox` is extracted from Overture `bbox` struct fields
  `(xmin=min_lon, ymin=min_lat, xmax=max_lon, ymax=max_lat)`

**Test:** `tests/unit/test_geo.py::test_koramangala_centroid` — asserts
`abs(centroid.lon - 77.62) < 0.05` and `abs(centroid.lat - 12.93) < 0.05`.
This test runs in every CI check.

---

## D-006 — Source Independence Model

**Decision date:** 2026-09-16  
**Status:** Accepted

Overture blends data from multiple contributors (Meta Places, Microsoft, Foursquare
Open Source Places, and in some cases OSM-derived data). Agreement between two
records counts as **independent confirmation** only if their `sources` lineage
differs:

- Overture record whose `sources[].dataset` includes only Meta/Microsoft
  AND an OSM record = **independent** (2 independent sources).
- Overture record derived from OSM (sources containing `openstreetmap`)
  AND an OSM record = **NOT independent** (same underlying data).
- Two Overture records from different lineages = **partially independent**
  (counted as 1.5, not 2).

`independent_source_count` on `businesses` reflects this model.
The `field_provenance` table records `lineage` per source for full auditability.

---

## D-007 — Reuse from KishoreRaman04/Data-Scraper-Project

**Decision date:** 2026-09-16  
**Status:** Accepted

The following components are ported:

| Component | v2 Use | Notes |
|---|---|---|
| Area JSON files (Bengaluru, Hyderabad, Mumbai, Chennai, Kochi, Karnataka districts) | `seeds/` + `area_seeds` table; autocomplete + batch mode | Schema: `{city, regions: {REGION: [Area]}}` |
| Keyword preset format (`MPSearchCategory.json` etc.) | `keyword_presets` table; preset import endpoint | `{search_categories, exclude_keywords}` |
| `is_address_in_area` + `DISTRICT_ALIASES` | Textual secondary check in N7; primary check is geometric | Ported as `verify/address_check.py` |
| `clean_phone_number` rules | Test cases for `phonenumbers`-based normaliser | All cases become unit tests |
| Checkpoint/resume idea | Superseded by LangGraph checkpoints | Batch-mode area tracking preserved |
| `excel_exporter.py` layout | XLSX export with attribution sheet | Ported to `app/api/export.py` |
| Media blocking | `DynamicFetcher` session config | Blocks images/fonts/media |

**Explicitly NOT ported:**
- Google Maps extraction path (prohibited by Google ToS).
- Any DOM selector tuned for Google Maps UI.

---

## D-008 — Metrics Honesty Contract

**Decision date:** 2026-09-16  
**Status:** Accepted, enforced in UI

Every metric in Section 3 carries a `kind` field:

| `kind` | Meaning | UI badge | Threshold to display |
|---|---|---|---|
| `ground_truth` | Computed from human labels, Wilson 95% CI, sample size `n` | **Measured** (green) | `n ≥ 30` per metric |
| `proxy` | Computed from cross-source agreement; auto-estimated | **Estimate** (yellow) | Always displayed |

**Non-negotiable rules:**
1. `ground_truth` metrics are hidden (replaced with "Label N more to unlock")
   until `n ≥ 30`.
2. Wilson 95% CI is always shown alongside ground-truth precision/recall/F1.
3. Capture-recapture coverage estimate always carries the caveat tooltip:
   "Sources are positively correlated; N̂ is likely an underestimate and
   proxy recall is optimistic."
4. The `scoring_model_version` is recorded on every run so historical metrics
   remain comparable.
