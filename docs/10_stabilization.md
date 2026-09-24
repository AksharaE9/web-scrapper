# LeadCore Zero — Backend Stabilization & Pipeline Reliability Report

**Status:** STABILIZED & VERIFIED  
**Date:** 2026-09-22  
**Architecture Version:** LeadCore Zero v2.1.0  

---

## 1. Executive Summary & Root Cause Resolutions

| ID | Issue | Root Cause | Implemented Resolution | Verification Evidence |
|---|---|---|---|---|
| **R1** | `ImportError` in N5 / API | `haversine_distance_m` deleted from `n1_geo` while lazily imported in `n5_resolve.py` and `api/leads.py`. | Created canonical `app/resolve/geo_math.py`; hoisted all imports to module level across all files. | `tests/test_imports.py` (AST + Dynamic Resolution) passing 100%. |
| **R2** | Phantom Worker Queue / Stalled Runs | `worker.py` had an empty `sleep(2)` loop with unmanaged `asyncio.create_task` calls. | Implemented PostgreSQL `FOR UPDATE SKIP LOCKED` leased queue with auto-reclaim, heartbeats, and task tracking. | Alembic revision `004_leased_worker_queue` + Active claim engine. |
| **R3** | Short & Bare-City Geo Failure | Acronyms (`hsr`, `btm`) < 4 chars failed fuzzy matching; bare cities penalized for missing localities. | Created `config/geo_aliases.yaml`; added shape-aware branching (`locality_in_city`, `city_only`, `region_only`). | Geo test ladder passing across acronyms & bare cities. |
| **R4** | Legacy Row Poisoning | Legacy rows with `raw_input: NULL` crashed workers. | Added quarantine in `worker.py` (`error_code='corrupt_run_row'`) and created `scripts/cleanup_legacy_runs.py`. | Corrupt rows fail gracefully without worker crashes. |

---

## 2. Leased Worker Queue Architecture

The worker pool operates on a distributed PostgreSQL lease pattern:

```sql
UPDATE query_runs
   SET status = 'running',
       started_at = COALESCE(started_at, NOW()),
       worker_id = %s,
       lease_until = NOW() + INTERVAL '15 minutes',
       updated_at = NOW()
 WHERE id IN (
     SELECT id FROM query_runs
      WHERE status = 'queued'
         OR (status = 'running' AND lease_until IS NOT NULL AND lease_until < NOW())
      ORDER BY created_at ASC
      FOR UPDATE SKIP LOCKED
      LIMIT %s
 )
RETURNING id;
```

### Key Safety Guarantees
1. **Zero Phantom Execution:** Every claimed run is tied to a `worker_id` and has a live heartbeat extending its lease.
2. **Crash Resilience:** If a worker process abruptly terminates, unrenewed leases expire and are automatically reclaimed by surviving workers on the next poll.
3. **Graceful Shutdown:** `stop()` cancels the polling loop, awaits in-flight tasks, and commits clean checkpoints.

---

## 3. Systematic Test Suite Evidence

### 1. Import & Symbol Integrity (`tests/test_imports.py`)
- `test_all_modules_importable`: Traverses the entire `app/` directory and confirms 100% clean top-level importability without circular errors.
- `test_ast_symbol_resolution`: Parses the AST of every first-party import statement (`from app.X import Y`) and validates that symbol `Y` exists on `app.X`.
- `test_no_unapproved_lazy_first_party_imports`: Verifies no unannotated inline imports exist inside functions.

### 2. Isolated Node Smoke Tests (`tests/graph/test_node_smoke.py`)
- **N4 (Relevance Cascade):** Confirms true positive preservation and hard gate vetoing.
- **N5 (Entity Resolution):** Verifies Splink Fellegi-Sunter clustering and `haversine_distance_m` distance calculation.
- **N6 (Enrichment):** Verifies phone/email extraction via deterministic parsing.
- **N7 (Verification):** Validates multi-point verification checks.
- **N8 (Scoring):** Asserts calibrated scoring and tier assignment (`Verified`, `Likely`, `Unverified`).
- **N10 (Persistence):** Validates PostGIS upsert and deduplication mechanics.

### 3. Pipeline Contract (`tests/graph/test_pipeline_contract.py`)
- Executes full LangGraph graph contract end-to-end with 20 sample candidates.
- Validates that state flows cleanly from `n0_input` $\to$ `n1_geo` $\to$ `n2_keyword` $\to$ sources $\to$ `n4_filter` $\to$ `n5_resolve` $\to$ `n8_score` $\to$ `n10_persist` $\to$ `n12_report`.
