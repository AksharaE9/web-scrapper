# LeadCore Zero — Test Strategy & QA Architecture

---

## 1. Overview & Objectives

This document establishes the test strategy, quality pyramid, coverage bars, and verification doctrine for LeadCore Zero v3.

**Core Mission:**
Ensure the lead-intelligence pipeline is **correct, honest, resumable, and precise**:
- No silent fallbacks or unmeasured metric reporting.
- Deterministic and reproducible offline evaluation.
- Full compliance with OSMF, Overpass, and DPDP usage rules.

---

## 2. The Test Pyramid & Layer Architecture

```
                    ┌──────────────────────────┐
                    │  E2E (Playwright)  ~15   │   Browser, seeded DB, cassettes
                    ├──────────────────────────┤
                    │  API / Contract    ~60   │   FastAPI TestClient + live Postgres
                    ├──────────────────────────┤
                    │  Integration       ~80   │   Graph nodes ↔ DB ↔ fake origin
                    ├──────────────────────────┤
                    │  Unit             ~250   │   Pure functions, 0 DB, 0 network
                    └──────────────────────────┘
   ── Scraper-Specific Orthogonal Test Layers ──
   Layer 1: LIVENESS & FRESHNESS   Verified socket accounting & egress ledger
   Layer 2: EDGE-CASE CATALOGUE    Hostile inputs, network pathologies, malformed markup
   Layer 3: DATA QUALITY & EVAL    Gold benchmark, calibration (ECE), Wilson intervals
```

---

## 3. Testing Principles & Doctrine

1. **The One Rule**: A test that cannot fail is not a test. Every suite requires a mutation proof demonstrating it catches broken behavior.
2. **No Live Network in Unit/Integration**: All external requests are mocked with recorded cassettes or routed to the ephemeral fake origin server. Real network calls are tagged `-m live`.
3. **Real Postgres (PostGIS + pgvector)**: No SQLite dialect emulation or mocks for spatial or vector math.
4. **Coverage Policy**:
   - `app/relevance/`: $\ge 90\%$ line coverage
   - `app/verify/`: $\ge 90\%$ line coverage
   - `app/resolve/`: $\ge 90\%$ line coverage
   - `app/db/geo_sql.py`: $\ge 95\%$ line coverage
   - Global repo floor: $\ge 75\%$ line coverage

---

## 4. Test Harness Infrastructure

### 4.1 Ephemeral Fake Origin Server (`tests/fixtures/origin/server.py`)
Simulates hostile internet behaviors deterministically on localhost:
- **Robots.txt Policies**: allow-all, disallow-all, 500 error (fail-closed), crawl-delay, 10MB junk file.
- **Structured Data**: valid JSON-LD (`LocalBusiness`), Microdata, RDFa, broken JSON-LD syntax.
- **Branch Disambiguation**: 12 branch addresses/phones on a single page.
- **Cache & Freshness**: 304 `ETag` and `Last-Modified`, rotating ETags, cosmetic-only changes (Simhash testing).
- **Security & Adversarial**: Prompt injection text (`<div style="display:none">Ignore previous instructions...</div>`), Cloudflare interstitial challenge markers, 50MB oversized payloads, chunked stalls.

### 4.2 Recorded Cassettes (`tests/fixtures/cassettes/`)
Deterministic replays of Overpass, Nominatim, and Photon responses, with zero PII.

---

## 5. Continuous Integration Gates

1. **Lint & Static Gate**: Ruff check, TypeScript check (`tsc --noEmit`), and static AST anti-silent-fallback check.
2. **Unit & Fast Integration Gate**: Pytest suite executing with egress blocked.
3. **Database & Schema Drift Gate**: `alembic check` and spatial/vector round-trip validation against PostGIS.
4. **Relevance Regression Gate**: `python -m app.eval.relevance --all` asserting no metric regression > 2 points against `baseline.json`.
5. **Compliance Gate**: Zero calls to forbidden domains, Nominatim $\le 1$ req/s, and no SMTP callback probing.
