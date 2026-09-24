"""
v3 schema additions — crawl_log and HNSW index tuning

Revision ID: 003_v3_schema
Revises: 002_relevance_engine
Create Date: 2026-09-22
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "003_v3_schema"
down_revision = "002_relevance_engine"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. crawl_log table
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS crawl_log (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            domain TEXT NOT NULL,
            url TEXT NOT NULL,
            http_status INT,
            outcome TEXT,
            robots_allowed BOOLEAN DEFAULT TRUE,
            etag TEXT,
            last_modified TEXT,
            simhash BIGINT,
            fetched_at TIMESTAMPTZ DEFAULT NOW()
        )
    """))

    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_crawl_log_url ON crawl_log(url)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_crawl_log_domain ON crawl_log(domain)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_crawl_log_fetched_at ON crawl_log(fetched_at DESC)"))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("DROP TABLE IF EXISTS crawl_log CASCADE"))
