"""
app/db/schema_contract.py — Database schema & migration contract enforcement at boot.

Ensures the application refuses to start if the database schema is missing required
columns or if Alembic migrations are pending.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from alembic.config import Config
from alembic.script import ScriptDirectory

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS: dict[str, set[str]] = {
    "query_runs": {
        "id",
        "created_at",
        "status",
        "raw_input",
        "locality",
        "city",
        "state",
        "country",
        "keywords",
        "exclude_keywords",
        "options",
        "error",
        "error_code",
        "worker_id",
        "lease_until",
        "started_at",
        "finished_at",
        "updated_at",
        "stats",
        "retryable",
        "attempt_count",
        "attempt_strategy",
        "parent_run_id",
        "completion_reason",
    },
    "businesses": {
        "id",
        "canonical_name",
        "name_norm",
        "primary_category",
        "categories",
        "phones_e164",
        "emails",
        "website_domain",
        "geom",
        "confidence",
        "tier",
        "updated_at",
    },
    "run_results": {
        "run_id",
        "business_id",
        "keyword",
        "match_score",
        "decision",
        "relevance_p",
        "relevance_stage",
        "relevance_features",
        "relevance_reasons",
        "concept_id",
        "concept_version",
    },
    "rejected_candidates": {
        "run_id",
        "source",
        "source_record_id",
        "name",
        "reason",
        "reason_code",
        "relevance_p",
        "features",
    },
    "keyword_concepts": {
        "concept_id",
        "version",
        "keyword_norm",
        "card",
        "embedding",
        "origin",
    },
    "concept_exemplars": {
        "id",
        "concept_id",
        "polarity",
        "text",
        "embedding",
        "origin",
    },
    "crawl_log": {
        "domain",
        "url",
        "fetched_at",
        "http_status",
        "outcome",
        "robots_allowed",
    },
    "business_sources": {
        "business_id",
        "source",
        "source_record_id",
        "fetched_at",
    },
}


def get_head_revision() -> str:
    """Read the latest migration revision from disk."""
    base_dir = Path(__file__).resolve().parent.parent.parent
    alembic_cfg_path = base_dir / "alembic.ini"
    if not alembic_cfg_path.exists():
        # Fallback to current working directory
        alembic_cfg_path = Path("alembic.ini").resolve()
    
    config = Config(str(alembic_cfg_path))
    script = ScriptDirectory.from_config(config)
    head = script.get_current_head()
    if not head:
        raise RuntimeError("No Alembic head revision found in migrations directory.")
    return head


async def assert_schema(conn: Any) -> None:
    """
    Verify all required tables and columns exist in information_schema.
    Raises RuntimeError on any missing table or column.
    """
    missing: list[str] = []
    for table, cols in REQUIRED_COLUMNS.items():
        res = await conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
            (table,),
        )
        rows = await res.fetchall()
        have = {r["column_name"] if isinstance(r, dict) else r[0] for r in rows}
        if not have:
            missing.append(f"{table} (table does not exist)")
        else:
            for c in sorted(cols - have):
                missing.append(f"{table}.{c}")

    if missing:
        raise RuntimeError(
            "Database schema is out of date — the application cannot start.\n"
            f"Missing: {', '.join(missing)}\n"
            "Run:  uv run alembic upgrade head"
        )


async def assert_migrations_current(conn: Any) -> None:
    """
    Verify that alembic_version in the database matches head migration on disk.
    Raises RuntimeError if migrations are pending.
    """
    head_rev = get_head_revision()
    res = await conn.execute("SELECT version_num FROM alembic_version LIMIT 1")
    row = await res.fetchone()
    db_rev = (row["version_num"] if isinstance(row, dict) else row[0]) if row else None

    if db_rev != head_rev:
        raise RuntimeError(
            "Database migration is out of date — the application cannot start.\n"
            f"Database revision: '{db_rev}'\n"
            f"Head revision:     '{head_rev}'\n"
            "Run:  uv run alembic upgrade head"
        )
