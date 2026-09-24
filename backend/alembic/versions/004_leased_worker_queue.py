"""
leased worker queue columns and indexes

Revision ID: 004_leased_worker_queue
Revises: 003_v3_schema
Create Date: 2026-09-22
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "004_leased_worker_queue"
down_revision = "003_v3_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Add worker_id, lease_until, and error_code to query_runs
    conn.execute(text("""
        ALTER TABLE query_runs
        ADD COLUMN IF NOT EXISTS worker_id TEXT,
        ADD COLUMN IF NOT EXISTS lease_until TIMESTAMPTZ,
        ADD COLUMN IF NOT EXISTS error_code TEXT;
    """))

    # 2. Add index for leased queue polling
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_query_runs_queue
        ON query_runs(status, lease_until, created_at);
    """))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("DROP INDEX IF EXISTS ix_query_runs_queue"))
    conn.execute(text("""
        ALTER TABLE query_runs
        DROP COLUMN IF EXISTS worker_id,
        DROP COLUMN IF EXISTS lease_until,
        DROP COLUMN IF EXISTS error_code;
    """))
