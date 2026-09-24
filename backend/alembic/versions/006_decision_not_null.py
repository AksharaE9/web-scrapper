"""
migration 006: decision NOT NULL, check constraint, and composite index on run_results

Revision ID: 006_decision_not_null
Revises: 005_self_healing_and_retryable
Create Date: 2026-09-23
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "006_decision_not_null"
down_revision = "005_self_healing_and_retryable"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Backfill any legacy NULL decisions
    conn.execute(text("""
        UPDATE run_results
           SET decision = 'accepted'
         WHERE decision IS NULL;
    """))

    # 2. Enforce NOT NULL on decision
    conn.execute(text("""
        ALTER TABLE run_results
        ALTER COLUMN decision SET NOT NULL;
    """))

    # 3. Add CHECK constraint on valid decision outcomes
    conn.execute(text("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'ck_run_results_decision'
            ) THEN
                ALTER TABLE run_results
                ADD CONSTRAINT ck_run_results_decision
                CHECK (decision IN ('accepted', 'review', 'rejected'));
            END IF;
        END $$;
    """))

    # 4. Add composite index on (run_id, decision, rank) for fast filtered list/export queries
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_run_results_run_decision_rank
        ON run_results(run_id, decision, rank);
    """))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("""
        DROP INDEX IF EXISTS ix_run_results_run_decision_rank;
        ALTER TABLE run_results DROP CONSTRAINT IF EXISTS ck_run_results_decision;
        ALTER TABLE run_results ALTER COLUMN decision DROP NOT NULL;
    """))
