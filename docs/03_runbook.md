# LeadCore Zero v2 — Phase Gate Evidence Runbook

This document records the acceptance-criteria evidence for each phase gate.
Evidence must be command output, test results, or screenshots — not claims.

---

## Phase 0 — Postmortem Gate

**Gate:** `docs/00_postmortem.md` exists and every failure mode item is marked
*applies / does not apply / unknown* with a reason.

**Status:** ✅ PASSED

**Evidence:**
- `docs/00_postmortem.md` created at `2026-09-16T11:22:52+05:30`
- All 7 failure modes (FM-1 through FM-7) marked "DOES NOT APPLY (old repo
  unavailable) → Treated as design requirement" with specific v2 prevention
  strategies and code locations.

---

## Phase 1 — Foundations Gate

**Gate:**
1. `make migrate` succeeds on a fresh Neon branch (extension versions reported)
2. `GET /api/health` shows Neon ok with extension versions
3. Frontend loads and calls health through configured CORS origin
4. Cold-start test: Neon suspended → connects within retry budget

**Status:** ⏳ PENDING — awaiting Neon credentials in `.env`

**Evidence:** *(to be pasted after running `make migrate` and starting the server)*

---

## Phase 2 — Geo + Keyword Planning Gate

**Gate:**
1. `pytest tests/unit/test_geo.py::test_koramangala_centroid -v` passes
2. "Kormangala, Karnataka, India" (misspelling) resolves to the correct boundary
3. An ambiguous input triggers the disambiguation picker
4. "gym", "coaching centre", and "pickleball court" all return plans with
   non-empty `name_patterns`
5. Nominatim mock clock test passes (rate ≤ 1 req/s)

**Status:** ⏳ PENDING

---

## Phase 3 — Sources Gate

**Gate:**
1. Gyms in Koramangala: both Overture and OSM log candidate counts > 0
2. Every accepted candidate is inside the boundary or flagged `edge_case=true`
3. Second locality in Bengaluru hits local Overture Parquet cache
4. Forcing Overpass endpoint 1 to fail triggers automatic failover
5. Removing a required Overture column in a fixture fails the schema gate with
   a clear error message

**Status:** ⏳ PENDING

---

## Phase 4 — Resolution + Persistence + Graph Runtime Gate

**Gate:**
1. One complete run produces: run card, leads table, lead drawer with provenance
2. Rerunning the same query: `SELECT COUNT(*) FROM businesses` shows zero new rows
3. Kill backend mid-run → restart → run resumes from last completed node
4. Same gym appearing in OSM and Overture appears once in `businesses` with both
   sources listed in `business_sources`

**Status:** ⏳ PENDING

---

## Phase 5 — Enrichment + Verification + Scoring Gate

**Gate:**
1. `pytest tests/integration/test_scrapling.py::test_robots_disallowed -v` passes
2. Fixture challenge page → `outcome=blocked_by_site`, no subsequent retries
3. `pytest tests/unit/test_grounded_extract.py::test_reject_field_without_quote -v` passes
4. Full run with `LLM_ENABLED=false` in `.env` completes successfully
5. All three tiers (Verified / Likely / Unverified) appear in the UI run card

**Status:** ⏳ PENDING

---

## Phase 6 — Metrics + Labelling Gate

**Gate:**
1. With < 30 labels: P/R/F1 tiles show "Label N more to unlock"; proxy tiles
   show the **Estimate** badge
2. After adding 30+ gold labels on a run fixture: precision/recall/F1/accuracy
   render with Wilson 95% CIs matching hand-computed values
3. Export (`GET /api/runs/{id}/export?format=xlsx`) excludes delivered and
   suppressed leads by default
4. XLSX file includes an "Attribution" sheet listing OSM ODbL and Overture licences

**Status:** ⏳ PENDING

---

## Phase 7 — Hardening Gate

**Gate:**
1. 20-area batch completes without manual intervention
2. `SELECT COUNT(*) FROM businesses` count is stable (no duplicates across areas)
3. `scripts/profile_run.py` output committed to `docs/profile_report.txt`
4. Rust decision documented: not needed (expected, unless profiler shows >30%
   Python hot loop in wall time)
5. Load test: 3 concurrent runs complete without deadlock or pool exhaustion

**Status:** ⏳ PENDING

---

## Smoke Test Results (manual, per Section 13)

*(To be recorded after Phase 5 is complete)*

### Test 1: Gyms · Koramangala, Karnataka, India

| Metric | Value |
|---|---|
| Overture candidates | — |
| OSM candidates | — |
| After filter | — |
| After resolution | — |
| Verified tier | — |
| Likely tier | — |
| Unverified tier | — |
| 30-label precision | — |

### Test 2: Salons · Banjara Hills, Telangana, India

| Metric | Value |
|---|---|
| Overture candidates | — |
| OSM candidates | — |
| After filter | — |
| After resolution | — |
| Tiers (V/L/U) | — |
| 30-label precision | — |

### Test 3: Coaching centres · Kukatpally, Telangana, India

| Metric | Value |
|---|---|
| Overture candidates | — |
| OSM candidates | — |
| After filter | — |
| After resolution | — |
| Tiers (V/L/U) | — |
| 30-label precision | — |
