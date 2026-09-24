"""
self healing runs, retryable metadata, target completion and guaranteed input integrity

Revision ID: 005_self_healing_and_retryable
Revises: 004_leased_worker_queue
Create Date: 2026-09-22
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "005_self_healing_and_retryable"
down_revision = "004_leased_worker_queue"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Backfill legacy NULL raw_input rows to avoid validation crash and mark unretryable
    conn.execute(text("""
        UPDATE query_runs
           SET raw_input = '{}'::jsonb,
               status = 'failed',
               error_code = 'corrupt_run_row',
               error = jsonb_build_object(
                 'code','corrupt_run_row',
                 'message','This run was created before input validation existed and cannot be re-run.',
                 'retryable', false),
               finished_at = COALESCE(finished_at, NOW())
         WHERE raw_input IS NULL;
    """))

    # 2. Add retryable, attempt_count, attempt_strategy, parent_run_id, completion_reason
    conn.execute(text("""
        ALTER TABLE query_runs
          ADD COLUMN IF NOT EXISTS retryable BOOLEAN NOT NULL DEFAULT TRUE,
          ADD COLUMN IF NOT EXISTS attempt_count INT NOT NULL DEFAULT 0,
          ADD COLUMN IF NOT EXISTS attempt_strategy TEXT,
          ADD COLUMN IF NOT EXISTS parent_run_id UUID REFERENCES query_runs(id) ON DELETE SET NULL,
          ADD COLUMN IF NOT EXISTS completion_reason TEXT;
    """))

    # 3. Mark backfilled legacy runs as retryable = false
    conn.execute(text("""
        UPDATE query_runs
           SET retryable = FALSE
         WHERE error_code = 'corrupt_run_row';
    """))

    # 4. Enforce NOT NULL and valid object shape constraint on raw_input
    conn.execute(text("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'ck_query_runs_raw_input_shape'
            ) THEN
                ALTER TABLE query_runs
                ADD CONSTRAINT ck_query_runs_raw_input_shape
                CHECK (raw_input IS NULL OR jsonb_typeof(raw_input::jsonb) = 'object');
            END IF;
        END $$;
    """))

    conn.execute(text("""
        ALTER TABLE query_runs ALTER COLUMN raw_input SET NOT NULL;
    """))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("""
        ALTER TABLE query_runs ALTER COLUMN raw_input DROP NOT NULL;
        ALTER TABLE query_runs DROP CONSTRAINT IF EXISTS ck_query_runs_raw_input_shape;
        ALTER TABLE query_runs
          DROP COLUMN IF EXISTS retryable,
          DROP COLUMN IF EXISTS attempt_count,
          DROP COLUMN IF EXISTS attempt_strategy,
          DROP COLUMN IF EXISTS parent_run_id,
          DROP COLUMN IF EXISTS completion_reason;
    """))
