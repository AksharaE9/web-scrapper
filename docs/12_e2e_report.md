# LeadCore Zero — End-to-End Test & Verification Report
**Generated:** 2026-09-23 04:41:25 UTC  
**Environment:** PostgreSQL (Neon) + Overture (DuckDB/Parquet) + Overpass (OSM)  
**Architecture:** Autonomous Self-Healing Graph Execution with 4-Layer Deduplication  

## Test Execution Matrix

| Case | Status | Duration | Total Leads | Accepted | Review | Dedup Unique | Completion Reason | Verdict |
|---|---|---|---|---|---|---|---|---|
| `pooja_store_hsr` | **COMPLETED** | 20.09s | 9 | 0 | 9 | 9 (100%) | `region_exhausted` | **PASS** |
| `hotels_banjara_hills` | **COMPLETED** | 54.06s | 15 | 4 | 11 | 15 (100%) | `target_met` | **PASS** |
| `coffee_indiranagar` | **COMPLETED** | 32.86s | 15 | 15 | 0 | 15 (100%) | `target_met` | **PASS** |
| `target_exhaustion` | **COMPLETED** | 32.77s | 19 | 0 | 19 | 19 (100%) | `region_exhausted` | **PASS** |
| `source_degraded` | **PARTIAL** | 35.67s | 10 | 9 | 1 | 10 (100%) | `target_met` | **PASS** |

## Core Guarantees & Verification Results

### 1. Zero Unexecutable Runs & Input Integrity (Phase 1)
- **Constraint Enforcement**: `raw_input` is enforced `NOT NULL` with object check constraint.
- **Corrupt Backlog Quarantine**: Legacy corrupt rows marked `retryable = FALSE`, preventing crash loops.
- **Server-Validated Rerun**: Rerun requests on unretryable records return HTTP 422 with prefill search parameters.

### 2. Self-Healing & Adaptive Retries (Phase 2)
- **Strategy Mutation**: Forced failovers switch strategy (`endpoint_failover`, `cache_fallback`, `boundary_widened`, `ladder_escalated`).
- **Partial Over Failure**: Pipeline runs with healthy sources or partial leads resolve as `PARTIAL` rather than failing.

### 3. Guaranteed Target Completion & Expansion Ladder (Phase 3)
- **Multi-Rung Escalation**: 6-rung expansion ladder executed when base candidate density is below target.
- **Area Exhaustion**: Exact region exhaustion message formatted and emitted upon ladder exhaustion.
- **Relevance Preservation**: Rungs 3+ route candidates strictly to the Review band.

### 4. 4-Layer Deduplication Guarantee (Phase 4)
- **Layer 1 (Source)**: Deduped on `(source, source_record_id)`.
- **Layer 2 (Cross-Source)**: Splink probabilistic clustering with geohash-7, phone, and domain blocking.
- **Layer 3 (Expansion Rungs)**: Accumulation set checked before every rung evaluation.
- **Layer 4 (Global Cross-Run)**: Proximity + name similarity merge into existing entities.
- **Export Guarantee**: 0 duplicate `business_id` or `(name, phone)` across all 5 runs.

### 5. Final Suite Verdict
**Overall Suite Status:** ✅ **ALL 5 SUITE CASES PASS**