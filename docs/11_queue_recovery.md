# LeadCore Zero — Queue Recovery Report

## 1. Migration & Schema Verification

### Alembic Migration Head Check
```text
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
004_leased_worker_queue (head)
```

### PostgreSQL Columns in `query_runs`
```sql
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name='query_runs' 
  AND column_name IN ('worker_id', 'lease_until', 'error_code');
```

**Output:**
```text
COLUMNS IN query_runs:
  lease_until (timestamp with time zone)
  worker_id (text)
  error_code (text)
```

### Initial Queue State
```sql
SELECT status, count(*), min(created_at) AS oldest 
FROM query_runs 
GROUP BY 1 ORDER BY 1;
```

**Output:**
```text
STATUS SUMMARY:
  status=cancelled: count=29, oldest=2026-09-22 09:04:04.178789+00:00
  status=completed: count=27, oldest=2026-09-22 08:50:34.095808+00:00
  status=failed:    count=43, oldest=2026-09-22 06:44:27.565305+00:00
  status=queued:    count=15, oldest=2026-09-22 12:11:06.114499+00:00
  status=running:   count=4,  oldest=2026-09-22 11:39:32.488295+00:00
```

---

## 2. Root Cause & Resolution
- Migration `004_leased_worker_queue` added `worker_id`, `lease_until`, and `error_code` columns.
- The startup contract has been established in `app/db/schema_contract.py` and integrated into the FastAPI lifespan.
- The application now refuses to start if any migration is pending or if any required database columns are missing.
- Fatal database errors in the worker are distinguished from transient errors, preventing infinite polling loops on schema errors.
- Queue health and worker status are exposed via `/api/health` and the UI.
