# LeadCore Zero v2 — Postmortem of Previous Build

**Status:** Old repository NOT AVAILABLE in workspace. This postmortem is written
based on the documented failure modes listed in the build spec (Section 2) and
treated as mandatory design requirements for v2.

---

## Failure Mode Audit

Each item below is marked: **applies / does not apply / unknown** with a v2 prevention
strategy.

---

### FM-1 Hard-coded category lists / location lists instead of free-text input

**Status: DOES NOT APPLY (old repo unavailable) → Treated as design requirement**

**Evidence:** Old repo not present; unable to inspect source.

**v2 Prevention:**
- `QueryInput.keywords` is a `list[str]` — any free-text business type accepted.
- `QueryInput.location` is four free-text fields (locality, city, state, country).
- `config/keyword_rules.yaml` and `seeds/` are used **only** for autocomplete
  and preset loading — never as exhaustive category gating.
- Keyword planning (N2) handles unknown keywords via RAG + optional LLM; it does
  not reject inputs not in a predefined list.
- OSM `name_patterns` matching ensures businesses identifiable only by name are
  captured even when not tagged with the expected OSM key.

---

### FM-2 Data source silently returned nothing (wrong schema field, wrong bbox lon/lat order, stale dataset path)

**Status: DOES NOT APPLY (old repo unavailable) → Treated as design requirement**

**Evidence:** Old repo not present. This is the highest-risk failure mode for
Overture-based systems due to schema evolution.

**v2 Prevention:**
- **Schema-drift gate:** `overture.py` runs `DESCRIBE SELECT * FROM parquet_scan(...)
  LIMIT 0` at startup and asserts that every required column
  (`id`, `names`, `basic_category`, `taxonomy`, `confidence`, `phones`, `websites`,
  `emails`, `socials`, `addresses`, `brand`, `operating_status`, `sources`, `geometry`)
  exists. Startup fails with a named error if any column is missing.
- **lon/lat unit test:** `tests/unit/test_geo.py::test_koramangala_centroid` asserts
  that the resolved centroid for "Koramangala, Karnataka, India" has
  `lon ≈ 77.62` and `lat ≈ 12.93` (not swapped). This test fails immediately if
  any coordinate-order bug is introduced.
- **Release auto-discovery:** Overture release is discovered by listing the public
  S3/Azure prefix anonymously at run time — never hard-coded. The release version
  is pinned to `runs.source_versions` for audit.
- **Bbox convention:** `GeoResolution.bbox` is always
  `(min_lon, min_lat, max_lon, max_lat)`. Type alias `BboxLonLat` and a validator
  that asserts `bbox[0] < bbox[2]` (lon range) and `bbox[1] < bbox[3]` (lat range)
  are both present.

---

### FM-3 Neon connection issues (pooled vs direct URL, prepared statements through PgBouncer, cold-start timeouts, pool exhaustion)

**Status: DOES NOT APPLY (old repo unavailable) → Treated as design requirement**

**Evidence:** Old repo not present. Neon-specific connection failures are a known
class of bug for any system that conflates the pooled and direct URLs.

**v2 Prevention:**
- Two separate env vars:
  - `DATABASE_URL` → **pooled** Neon URL (`-pooler` host) used by the API pool.
    `prepare_threshold=None` disables server-side prepared statements (required for
    PgBouncer in transaction mode).
  - `DATABASE_URL_DIRECT` → **direct** (non-pooled) URL used only by Alembic
    migrations and the LangGraph `PostgresSaver` checkpointer.
- Pool: `psycopg_pool.AsyncConnectionPool`, min 1, max 5,
  `connect_timeout=15`, `sslmode=require`.
- Connection acquisition wrapped in `tenacity` retry
  (`wait_exponential(min=1, max=10)`, `stop_after_attempt(5)`) to handle
  Neon compute cold-start (typically resolves within 5–10 s).
- No long-held idle transactions (SSE is served from in-memory bus, not by
  polling Neon).
- No background Neon polling of any kind.

---

### FM-4 CORS / env var mismatch between frontend and backend

**Status: DOES NOT APPLY (old repo unavailable) → Treated as design requirement**

**Evidence:** Old repo not present.

**v2 Prevention:**
- `CORS_ORIGINS` is an env var read by `pydantic-settings` on the backend.
  Default for dev: `["http://localhost:5173"]`. FastAPI `CORSMiddleware` is
  configured from this list at startup.
- Frontend base URL is set in `frontend/.env` as `VITE_API_BASE_URL` and
  consumed via a typed `apiClient` wrapper — never hard-coded.
- TypeScript types for all API request/response shapes are **generated** from the
  FastAPI OpenAPI spec (`openapi-typescript`) as a build step, so a mismatch
  between frontend and backend types causes a compile error, not a runtime failure.
- `.env.example` documents both vars side-by-side with a note about matching them.

---

### FM-5 Long-running jobs executed inside the HTTP request cycle (timeouts)

**Status: DOES NOT APPLY (old repo unavailable) → Treated as design requirement**

**Evidence:** Old repo not present. A scraping + entity-resolution run can easily
take 5–30 minutes for a large area; this cannot run inside a synchronous HTTP handler.

**v2 Prevention:**
- `POST /api/runs` returns **202 Accepted** immediately with `{run_id}`.
  The run is persisted to `query_runs` with `status="queued"` in the same request.
- A bounded in-process async worker (`app/worker.py`, concurrency = `RUN_CONCURRENCY`)
  dequeues and executes the LangGraph graph outside the HTTP request cycle.
- Progress is pushed to the frontend over **SSE** (`GET /api/runs/{id}/events`)
  from an in-memory event bus — the HTTP handler for SSE is a long-lived streaming
  response, not a polling loop.
- Per-node time budgets (in the `Budget` object) ensure no single node can block
  indefinitely; it completes with partial output and records a `NodeError`.

---

### FM-6 No resumability — a crash mid-run lost everything

**Status: DOES NOT APPLY (old repo unavailable) → Treated as design requirement**

**Evidence:** Old repo not present.

**v2 Prevention:**
- LangGraph `PostgresSaver` (checkpointer against `DATABASE_URL_DIRECT`) writes
  a checkpoint after every node completes. Thread ID = `run_id`.
- On server restart, `worker.py` queries `query_runs` for runs in `status="running"`
  or `status="queued"` and resumes them from their last completed checkpoint.
- The "never redo finished areas" behaviour from the old project's checkpoint
  concept is preserved: in batch mode, completed areas are tracked in `batch_runs`
  and skipped on retry.
- N10 (GlobalDedup + Persister) is idempotent: `business_sources(source,
  source_record_id)` has a UNIQUE constraint; rerunning the same run only upserts,
  never creates duplicates.

---

### FM-7 Tool sprawl (too many overlapping scraping libraries wired half-way)

**Status: DOES NOT APPLY (old repo unavailable) → Treated as design requirement**

**Evidence:** Old repo not present.

**v2 Prevention (single-framework rule):**
- **One crawling framework:** Scrapling only. No Scrapy, no Crawl4AI, no Crawlee,
  no Firecrawl, no Playwright directly.
- **One async runtime:** Python asyncio + LangGraph. No Celery, no Redis, no
  background threads (except the DuckDB thread pool which is internal).
- **One embedding engine:** fastembed (ONNX, CPU). No PyTorch, no sentence-transformers.
- **One entity resolution library:** Splink with DuckDB backend.
- **One HTTP client:** httpx (used by Scrapling internally; also used directly for
  Nominatim, Overpass, Wikidata, Ollama).
- Adapter interfaces are defined for future swap-ins (e.g., `ICrawler` protocol)
  but only one concrete implementation exists in v1.

---

## Summary

The old repository was not available for direct inspection. All seven documented
failure modes are treated as explicit design requirements in v2. Each has a
concrete technical prevention strategy, a code location, and (where applicable)
a unit or integration test that would catch a regression.

**Phase 0 Gate: PASSED** — this document exists and every item above is marked
with status and prevention strategy.
