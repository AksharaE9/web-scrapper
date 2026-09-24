# LeadCore Zero — Living Architecture Graph
Last updated: 2026-09-23 · Updated by: Principal AI/ML Engineer & Senior Frontend Architect · Status: Active Source of Truth

---

## 1. System Map

```mermaid
flowchart LR
  subgraph FE["Frontend · React 18 + Vite + Tailwind"]
    direction TB
    SP["ScrapePage"]:::impl
    LRP["LiveRunPanel"]:::impl
    RD["RunDetailPage"]:::impl
    LT["LeadsTable"]:::impl
    LD["LeadDrawer"]:::impl
    EB_R["RouteErrorBoundary"]:::impl
    EB_S["SectionErrorBoundary"]:::impl
    EB_ROW["RowErrorBoundary"]:::impl
  end

  subgraph API["FastAPI Application"]
    direction TB
    RUNS["POST /api/runs"]:::impl
    SSE["GET /api/runs/:id/events (SSE)"]:::impl
    LEADS["GET /api/runs/:id/leads"]:::impl
    RUN_GET["GET /api/runs/:id"]:::impl
    CFG["GET /api/config/*"]:::impl
  end

  subgraph WORKER["Leased Worker & Queue"]
    Q[("query_runs\n(FOR UPDATE SKIP LOCKED)")]:::impl
    POLL["Worker Loop (poll & lease)"]:::impl
  end

  subgraph GRAPH["LangGraph Pipeline DAG"]
    direction TB
    N0["N0 Input / Preflight"]:::impl --> N1["N1 Geo Resolution"]:::impl & N2["N2 Keyword Planner"]:::impl
    N1 -.->|"geo_conf < 0.6"| INT["disambiguation_interrupt"]:::impl -.-> N1
    N1 -->|"geo_conf >= 0.6"| JOIN["join_geo_kw"]:::impl
    N2 --> JOIN
    JOIN --> N3A["N3a Overture Source"]:::impl & N3B["N3b Overpass OSM"]:::impl & N3C["N3c Wikidata"]:::impl & N3D["N3d AllThePlaces"]:::stub & N3E["N3e Custom Imports"]:::impl
    N3A & N3B & N3C & N3D & N3E --> N4["N4 Relevance & Filter"]:::impl
    N4 --> N5["N5 Spatial & Deduplication"]:::impl
    N5 --> N6["N6 Web Crawl & Extract"]:::impl
    N6 --> N7["N7 Multi-Source Verify"]:::impl
    N7 --> N8["N8 Composite Scorer"]:::impl
    N8 --> N9["N9 Quality Critic"]:::stub
    N9 -.->|"critic loop (iter < 2)"| N6
    N9 -->|"pass"| N10["N10 DB Persist & Upsert"]:::impl
    N10 --> N11["N11 Eval & Metrics"]:::impl
    N11 --> N12["N12 Report & SSE Broadcast"]:::impl
  end

  subgraph DB["Neon PostgreSQL (PostGIS + pgvector)"]
    direction TB
    T_QR["query_runs"]:::impl
    T_RR["run_results"]:::impl
    T_BIZ["businesses"]:::impl
    T_EVT["run_events"]:::impl
    T_MET["run_metrics"]:::impl
  end

  SP --> RUNS --> Q --> POLL --> GRAPH
  GRAPH -.->|"Event Stream"| SSE -.-> LRP
  RD --> LEADS --> T_RR & T_BIZ
  RD --> RUN_GET --> T_QR
  N10 --> T_QR & T_RR & T_BIZ & T_EVT & T_MET

  classDef impl fill:#0e3b2e,stroke:#1baf7a,color:#e8f5f0
  classDef stub fill:#3b2e0e,stroke:#eda100,color:#f5f0e8
  classDef disc fill:#3b0e14,stroke:#e34948,color:#f5e8ea
```

---

## 2. Component Register

| ID | Component Name | Source File | Status | Contract In → Out | Test Coverage | Notes |
|:---|:---|:---|:---|:---|:---|:---|
| **N0** | Input Normalizer | `app/graph/nodes/n0_input.py` | `implemented` | `RunState` (raw query) → `RunState` (normalized `QueryInput`) | `tests/test_plan.py` | Validates query format, sets initial budget |
| **N1** | Geo Resolver | `app/graph/nodes/n1_geo.py` | `implemented` | `QueryInput.location` → `GeoResolution` (bbox, geom, confidence) | `tests/geo/`, `tests/test_geo.py` | Uses Nominatim + local Indian gazetteer fallback |
| **INT** | Disambiguation Interrupt | `app/graph/nodes/n1_geo.py` | `implemented` | Low geo confidence (<0.6) → Human choice → Resumed `GeoResolution` | `tests/geo/test_disambiguation.py` | LangGraph `interrupt()` pause/resume |
| **JOIN** | Geo-Keyword Join | `app/graph/build.py` | `implemented` | `GeoResolution` + `KeywordPlan` → Fan-out router | `tests/graph/test_graph_structure.py` | Pass-through synchronization barrier |
| **N2** | Keyword Planner | `app/graph/nodes/n2_keyword.py` | `implemented` | `QueryInput.keywords` → `KeywordPlan` (expansions, categories) | `tests/test_plan.py` | Multilingual & semantic category expansion |
| **N3a** | Overture Source Connector | `app/graph/nodes/n3a_overture.py` | `implemented` | `GeoResolution` bbox + `KeywordPlan` → `list[RawEntity]` | `tests/test_sources.py` | DuckDB spatial query over Parquet partitions |
| **N3b** | Overpass OSM Connector | `app/graph/nodes/n3b_overpass.py` | `implemented` | `GeoResolution` polygon → `list[RawEntity]` | `tests/test_sources.py` | Overpass QL with local caching & retry |
| **N3c** | Wikidata Connector | `app/graph/nodes/n3c_wikidata.py` | `implemented` | `GeoResolution` + `KeywordPlan` → `list[RawEntity]` | `tests/test_sources.py` | SPARQL query for notable entities |
| **N3d** | AllThePlaces Connector | `app/graph/nodes/n3d_alltheplaces.py` | `stub` | `GeoResolution` → `list[RawEntity]` | `tests/test_sources.py` | Spider scrapers stubbed for future expansion |
| **N3e** | Custom Imports Connector | `app/graph/nodes/n3e_imports.py` | `implemented` | Seed data / CSV uploads → `list[RawEntity]` | `tests/test_imports.py` | Custom user-supplied lead lists |
| **N4** | Relevance Filter | `app/graph/nodes/n4_relevance.py` | `implemented` | `list[RawEntity]` → Filtered entities with `relevance_p`, `decision` | `tests/relevance/`, `tests/eval/` | Multi-criteria keyword & category matching |
| **N5** | Spatial Resolver & Dedup | `app/graph/nodes/n5_resolve.py` | `implemented` | Merged entities → Deduplicated canonical entities | `tests/db/test_dedup_rules.py`, `tests/test_resolver.py` | Haversine distance + Jaro-Winkler string similarity |
| **N6** | Web Crawl & Enrichment | `app/graph/nodes/n6_enrich.py` | `implemented` | Canonical entities → Enriched (phones, emails, socials) | `tests/compliance/` | Rate-limited crawling with robots.txt adherence |
| **N7** | Multi-Source Verification | `app/graph/nodes/n7_verify.py` | `implemented` | Enriched entities → Verification badges, freshness scores | `tests/freshness/`, `tests/compliance/` | Validates domains, SSL, phone formats |
| **N8** | Composite Lead Scorer | `app/graph/nodes/n8_score.py` | `implemented` | Verified entities → Tier ranking (A/B/C/D), score `[0..1]` | `tests/eval/` | Weighted scoring model |
| **N9** | Quality Critic | `app/graph/nodes/n9_critic.py` | `stub` | Borderline scored leads → Re-enrich loop or proceed | `tests/test_critic.py` | Loop-back control under budget limit |
| **N10** | Database Persistence | `app/graph/nodes/n10_persist.py` | `implemented` | Scored leads → Postgres `businesses` & `run_results` upsert | `tests/db/test_schema_contract.py` | Atomic batch upsert with PostGIS geometry |
| **N11** | Evaluation & Calibration | `app/graph/nodes/n11_eval.py` | `implemented` | `run_results` → Wilson score intervals, precision metrics | `tests/eval/` | Statistical evaluation of run yield |
| **N12** | Summary Reporter & Events | `app/graph/nodes/n12_report.py` | `implemented` | Evaluation → Final `query_runs` status & terminal SSE event | `tests/e2e/test_full_pipeline.py` | Closes SSE channel, writes completion audit |
| **API-RUN** | Run Management API | `app/api/runs.py` | `implemented` | HTTP POST/GET → Queue run / return run details | `tests/api/` | FastAPI routes with validation & error handling |
| **API-LEAD**| Leads Query API | `app/api/leads.py` | `implemented` | Filter & tab query → Paginated envelope `{items, total}` | `tests/api/` | Supports decision tabs & text search |
| **FE-ROUT** | Frontend Router & Shell | `frontend/src/app/router.tsx` | `implemented` | URL navigation → Route pages wrapped in `RouteErrorBoundary` | `frontend build` | Top-level routing & crash resilience |
| **FE-LIVE** | Live Run Panel | `frontend/src/features/scrape/LiveRunPanel.tsx` | `implemented` | SSE stream → Dynamic graph, live ticker, source status | `frontend build` | Safe rendering of live event stream |
| **FE-TAB**  | Leads Table Component | `frontend/src/features/runs/LeadsTable.tsx` | `implemented` | Lead array → Filterable table with per-row error boundaries | `frontend build` | 4 distinct empty states, copy JSON, drawer trigger |

---

## 3. Data Contracts

### 3.1 `ChipDescriptor` (Frontend UI Contract)
```typescript
export interface ChipDescriptor {
  type: "positive" | "negative" | "weak" | "info";
  label: string;
  icon?: React.ReactNode;      // Must be a ReactNode or undefined — never a raw object
  weight?: number;
  detail?: string;
}
```

### 3.2 `Lead` (API Envelope & Client Contract)
```typescript
export interface Lead {
  id: string;
  run_id: string;
  business_id: string;
  canonical_name: string;
  primary_category: string;
  address?: string;
  locality?: string;
  city?: string;
  state?: string;
  postal_code?: string;
  country?: string;
  lat?: number;
  lng?: number;
  phones_e164: string[];
  emails: string[];
  websites: string[];
  socials: Record<string, string>;
  tier: "A" | "B" | "C" | "D";
  score: number;
  relevance_p: number;
  decision: "accepted" | "review" | "rejected";
  relevance_reasons: ChipDescriptor[] | string[];
  verification_status: Record<string, unknown>;
  rank: number;
  created_at: string;
}

export interface PaginatedLeadsResponse {
  items: Lead[];
  total: number;
  next_cursor?: string | null;
}
```

### 3.3 Server-Sent Events (`SSEEvent`)
```json
{
  "type": "lead_accepted" | "lead_rejected" | "node_started" | "node_completed" | "run_completed" | "run_failed" | "heartbeat",
  "run_id": "uuid",
  "timestamp": "ISO-8601",
  "data": {
    "node_id": "n4_filter",
    "elapsed_ms": 342,
    "lead": { ... },
    "metrics": { ... }
  }
}
```

---

## 4. Data Flow Sequences

### 4.1 Create Run Journey
```mermaid
sequenceDiagram
  autonumber
  actor User
  participant FE as Frontend (ScrapePage)
  participant API as FastAPI (/api/runs)
  participant DB as Neon DB (query_runs)
  participant Worker as Leased Worker

  User->>FE: Enter "pooja store", "HSR Layout", Submit
  FE->>API: POST /api/runs (QueryInput)
  API->>DB: INSERT INTO query_runs (status='queued')
  API-->>FE: HTTP 201 {run_id: "...", status: "queued"}
  FE->>FE: Navigate to /runs/:id (Live Stream View)
  Worker->>DB: SELECT FOR UPDATE SKIP LOCKED
  DB-->>Worker: Lease query_run record
  Worker->>Worker: Execute LangGraph Pipeline
```

### 4.2 Live Stream & Ticker Journey
```mermaid
sequenceDiagram
  autonumber
  actor User
  participant FE as Frontend (LiveRunPanel)
  participant SSE as FastAPI (/api/runs/:id/events)
  participant Worker as Leased Worker

  FE->>SSE: GET /api/runs/:id/events (EventSource)
  loop Pipeline Execution
    Worker->>SSE: Emit node_started, lead_accepted, node_completed
    SSE-->>FE: Stream SSEEvent payload
    FE->>FE: Update NodeGraph state & Live Influx counters
  end
  Worker->>SSE: Emit run_completed (completion_reason="region_exhausted")
  SSE-->>FE: Stream run_completed
  FE->>FE: Render completion summary & unlock Leads View
```

### 4.3 View Leads & Reconcile Journey
```mermaid
sequenceDiagram
  autonumber
  actor User
  participant FE as Frontend (RunDetailPage)
  participant API as FastAPI (/api/runs/:id/leads)
  participant DB as Neon DB (run_results + businesses)

  User->>FE: Click "Accepted (19)" tab (/runs/:id?tab=accepted)
  FE->>API: GET /api/runs/:id/leads?decision=accepted
  API->>DB: SELECT * FROM run_results JOIN businesses WHERE decision='accepted'
  DB-->>API: 19 records
  API-->>FE: Envelope {items: [19 leads], total: 19}
  FE->>FE: Reconcile tab count (19 == 19)
  FE->>FE: Render LeadsTable (each row wrapped in RowErrorBoundary)
```

### 4.4 Retry Failed Run Journey
```mermaid
sequenceDiagram
  autonumber
  actor User
  participant FE as Frontend (RunCard / ErrorBanner)
  participant API as FastAPI (/api/runs/:id/retry)
  participant DB as Neon DB

  User->>FE: Click "Retry Run"
  FE->>API: POST /api/runs/:id/retry
  API->>DB: UPDATE query_runs SET status='queued', retry_count = retry_count + 1
  API-->>FE: HTTP 200 {run_id: "...", status: "queued"}
  FE->>FE: Re-open live SSE stream
```

---

## 5. Database ER Diagram

```mermaid
erDiagram
  QUERY_RUNS ||--o{ RUN_RESULTS : "produces"
  QUERY_RUNS ||--o{ RUN_EVENTS : "logs"
  QUERY_RUNS ||--o{ RUN_METRICS : "measures"
  BUSINESSES ||--o{ RUN_RESULTS : "referenced_by"
  BUSINESSES ||--o{ LEAD_SOURCES : "originated_from"

  QUERY_RUNS {
    uuid id PK
    string query_text
    jsonb location_json
    string status "queued | running | completed | failed | cancelled"
    string completion_reason "target_reached | region_exhausted | budget_exceeded | failed"
    int lead_target
    int accepted_count
    int review_count
    int rejected_count
    timestamp created_at
    timestamp started_at
    timestamp finished_at
    string error_code
    string error_message
  }

  BUSINESSES {
    uuid id PK
    string canonical_name
    geometry geom "Point(lng, lat) SRID 4326"
    string primary_category
    string address_line
    string locality
    string city
    string state
    string postal_code
    string[] phones_e164
    string[] emails
    string[] websites
    jsonb raw_attributes
    timestamp created_at
    timestamp updated_at
  }

  RUN_RESULTS {
    uuid id PK
    uuid run_id FK
    uuid business_id FK
    string decision "accepted | review | rejected"
    float relevance_p
    jsonb relevance_reasons
    string tier "A | B | C | D"
    float score
    int rank
    timestamp created_at
  }

  RUN_EVENTS {
    uuid id PK
    uuid run_id FK
    string event_type
    jsonb payload
    timestamp created_at
  }

  RUN_METRICS {
    uuid id PK
    uuid run_id FK
    string metric_name
    float metric_value
    jsonb metadata
    timestamp created_at
  }

  LEAD_SOURCES {
    uuid id PK
    uuid business_id FK
    string source_name "overture | osm | wikidata | custom"
    string source_record_id
    jsonb raw_payload
    timestamp fetched_at
  }
```

---

## 6. Source Lineage & Ingestion Topology

```mermaid
flowchart TD
  subgraph EXTERNAL["External Data Sources"]
    OVT["Overture Places\n(Parquet / DuckDB)"]
    OSM["OpenStreetMap / Overpass\n(Overpass API)"]
    WKD["Wikidata POIs\n(SPARQL Endpoint)"]
    ATP["AllThePlaces Spider Spiders\n(GeoJSON)"]
    CSV["Custom Uploads / Seeds\n(CSV / JSONL)"]
  end

  subgraph NORMALIZATION["Schema Normalization"]
    N_OVT["Normalize Overture Schema"]
    N_OSM["Normalize OSM Tags"]
    N_WKD["Normalize Wikidata Claims"]
    N_ATP["Normalize Spider JSON"]
    N_CSV["Normalize Custom Fields"]
  end

  subgraph DEDUP["Entity Deduplication & Conflation (N5)"]
    HAV["Spatial Proximity (Haversine < 50m)"]
    JARO["Name Similarity (Jaro-Winkler > 0.85)"]
    CONFLATE["Conflate Attributes & Phone Merging"]
  end

  subgraph CANONICAL["Canonical Entity Record"]
    BIZ["Canonical Business Record (businesses table)"]
  end

  OVT --> N_OVT --> HAV
  OSM --> N_OSM --> HAV
  WKD --> N_WKD --> HAV
  ATP --> N_ATP --> HAV
  CSV --> N_CSV --> HAV

  HAV --> JARO --> CONFLATE --> BIZ
```

---

## 7. State Machines

### 7.1 `RunStatus` State Machine
```mermaid
stateDiagram-v2
  [*] --> queued : Run Submitted (POST /api/runs)
  queued --> running : Worker Leases (SKIP LOCKED)
  running --> completed : Pipeline Terminates (region_exhausted | target_reached)
  running --> failed : Uncaught Exception / Timeout / Budget Exceeded
  queued --> cancelled : User Abort
  running --> cancelled : User Abort
  failed --> queued : User Clicks "Retry Run"
  completed --> [*]
  failed --> [*]
  cancelled --> [*]
```

### 7.2 `NodeState` State Machine (Frontend UI)
```mermaid
stateDiagram-v2
  [*] --> pending : Initial State / Graph Mount
  pending --> running : node_started event received
  running --> done : node_completed event received OR duration_ms > 0
  running --> failed : node_failed event received
  pending --> skipped : Node bypassed by router condition
  failed --> [*]
  done --> [*]
  skipped --> [*]
```

---

## 8. Frontend Component Tree & Error Boundaries

```mermaid
flowchart TD
  ROOT["AppRoot / Router"]
  REB["RouteErrorBoundary (Catches route crashes, keeps shell & nav)"]
  NAV["App Header & Navigation Bar"]
  PAGE["Route Content (ScrapePage / RunDetailPage / ConfigPage)"]

  ROOT --> REB
  REB --> NAV
  REB --> PAGE

  subgraph RUN_DETAIL["RunDetailPage Tree"]
    SEB_MET["SectionErrorBoundary (Header & Stats)"]
    SEB_LRP["SectionErrorBoundary (LiveRunPanel)"]
    SEB_TAB["SectionErrorBoundary (LeadsTable & Tabs)"]
    
    PAGE --> SEB_MET
    PAGE --> SEB_LRP
    PAGE --> SEB_TAB

    subgraph TABLE["LeadsTable Tree"]
      ROW_LIST["Virtual Lead Row List"]
      ROW_EB1["RowErrorBoundary (Lead #1)"]
      ROW_EB2["RowErrorBoundary (Lead #2)"]
      ROW_EBN["RowErrorBoundary (Lead #N)"]
      
      SEB_TAB --> ROW_LIST
      ROW_LIST --> ROW_EB1
      ROW_LIST --> ROW_EB2
      ROW_LIST --> ROW_EBN
    end
  end
```

---

## 9. Decision Log

| Date | Decision | Alternatives Considered | Rationale | Decided By |
|:---|:---|:---|:---|:---|
| 2026-09-23 | Enforce `ChipDescriptor` and `renderSafe` across frontend | Ad-hoc object mapping or ignoring undefined types | Prevents React child object runtime crashes and guarantees graceful UI degradation | Principal Frontend Architect |
| 2026-09-23 | Granular 3-tier Error Boundary hierarchy | Global boundary only | Isolates bad row/panel render faults without destroying entire page state | Senior Frontend Architect |
| 2026-09-23 | Display exhaustion banner alongside leads table | Display banner instead of leads | Exhaustion is a valid result state, not an error; user must see yielded leads | Principal AI/ML Engineer |
| 2026-09-23 | Derive `NodeState` from unified function `deriveNodeState` | Dual-source status from event string and duration | Eliminates bug where finished nodes with duration showed "Pending" | Senior Frontend Architect |
| 2026-09-23 | Delegate microcopy & color token selection to Laya AI | Hardcoded decisions or manual prompt iterations | Streamlines local reversible styling choices under strict architectural boundaries | Principal Engineer (confirmed) |

---

## 10. Known Gaps

| Rank | Known Gap | Affected Component | Owner | Verification Test | Status |
|:---|:---|:---|:---|:---|:---|
| 1 | Quality Critic (N9) loop is currently a pass-through stub | `app/graph/nodes/n9_critic.py` | AI/ML Team | `tests/graph/test_critic_loop.py` | `stub` |
| 2 | AllThePlaces (N3d) spiders not yet fully integrated | `app/graph/nodes/n3d_alltheplaces.py` | Data Engineering | `tests/sources/test_alltheplaces.py` | `stub` |
| 3 | Automated Wilson confidence interval calibration | `app/graph/nodes/n11_eval.py` | ML Science | `tests/eval/test_wilson_metrics.py` | `partial` |
