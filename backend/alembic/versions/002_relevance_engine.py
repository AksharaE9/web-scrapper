"""
Relevance Engine schema migration — LeadCore Zero v2.1

Adds:
- query_runs.updated_at column (A3 fix)
- keyword_concepts table with versioning and embeddings
- keyword_aliases table
- concept_exemplars table for few-shot prototypes & hard negative mining
- osm_tag_vectors table
- llm_cache table
- run_results relevance columns (decision, relevance_p, relevance_stage, relevance_features, relevance_reasons, concept_id, concept_version, scorer_version)
- rejected_candidates relevance columns (reason_code, relevance_p, features)
- Indexes (HNSW cosine, btree)
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "002_relevance_engine"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def _check_halfvec_support(conn: sa.Connection) -> bool:
    """Return True if installed pgvector supports halfvec (>= 0.7.0)."""
    try:
        result = conn.execute(
            text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        ).fetchone()
        if result is None:
            return False
        version = result[0]
        parts = [int(x) for x in version.split(".")]
        return (parts[0], parts[1]) >= (0, 7)
    except Exception:
        return False


def upgrade() -> None:
    conn = op.get_bind()
    halfvec_ok = _check_halfvec_support(conn)
    vec_type = "halfvec(384)" if halfvec_ok else "vector(384)"

    # 1. query_runs.updated_at
    conn.execute(text("ALTER TABLE query_runs ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()"))

    # 2. keyword_concepts
    conn.execute(text(f"""
        CREATE TABLE IF NOT EXISTS keyword_concepts (
            concept_id TEXT NOT NULL,
            version INT NOT NULL,
            keyword_norm TEXT NOT NULL,
            card JSONB NOT NULL,
            embedding {vec_type},
            origin TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            PRIMARY KEY (concept_id, version)
        )
    """))
    conn.execute(text(
        f"CREATE INDEX IF NOT EXISTS ix_keyword_concepts_embedding ON keyword_concepts USING HNSW(embedding "
        f"{'halfvec_cosine_ops' if halfvec_ok else 'vector_cosine_ops'})"
    ))

    # 3. keyword_aliases
    op.create_table(
        "keyword_aliases",
        sa.Column("keyword_norm", sa.Text(), primary_key=True),
        sa.Column("concept_id", sa.Text(), nullable=False),
    )

    # 4. concept_exemplars
    conn.execute(text(f"""
        CREATE TABLE IF NOT EXISTS concept_exemplars (
            id BIGSERIAL PRIMARY KEY,
            concept_id TEXT NOT NULL,
            polarity SMALLINT NOT NULL,
            text TEXT NOT NULL,
            embedding {vec_type},
            origin TEXT,
            source_business_id UUID NULL,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """))
    conn.execute(text(
        f"CREATE INDEX IF NOT EXISTS ix_concept_exemplars_embedding ON concept_exemplars USING HNSW(embedding "
        f"{'halfvec_cosine_ops' if halfvec_ok else 'vector_cosine_ops'})"
    ))
    op.create_index("ix_concept_exemplars_concept_polarity", "concept_exemplars", ["concept_id", "polarity"])

    # 5. osm_tag_vectors
    conn.execute(text(f"""
        CREATE TABLE IF NOT EXISTS osm_tag_vectors (
            tag TEXT PRIMARY KEY,
            description TEXT,
            embedding {vec_type}
        )
    """))
    conn.execute(text(
        f"CREATE INDEX IF NOT EXISTS ix_osm_tag_vectors_embedding ON osm_tag_vectors USING HNSW(embedding "
        f"{'halfvec_cosine_ops' if halfvec_ok else 'vector_cosine_ops'})"
    ))

    # 6. llm_cache
    op.create_table(
        "llm_cache",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("response", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=text("NOW()")),
    )

    # 7. alter run_results
    conn.execute(text("""
        ALTER TABLE run_results
            ADD COLUMN IF NOT EXISTS decision TEXT CHECK (decision IN ('accepted','review','rejected')),
            ADD COLUMN IF NOT EXISTS relevance_p REAL,
            ADD COLUMN IF NOT EXISTS relevance_stage TEXT,
            ADD COLUMN IF NOT EXISTS relevance_features JSONB,
            ADD COLUMN IF NOT EXISTS relevance_reasons JSONB,
            ADD COLUMN IF NOT EXISTS concept_id TEXT,
            ADD COLUMN IF NOT EXISTS concept_version INT,
            ADD COLUMN IF NOT EXISTS scorer_version TEXT
    """))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_run_results_run_decision_p ON run_results(run_id, decision, relevance_p DESC)"
    ))

    # 8. alter rejected_candidates
    conn.execute(text("""
        ALTER TABLE rejected_candidates
            ADD COLUMN IF NOT EXISTS reason_code TEXT,
            ADD COLUMN IF NOT EXISTS relevance_p REAL,
            ADD COLUMN IF NOT EXISTS features JSONB
    """))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("DROP TABLE IF EXISTS llm_cache CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS osm_tag_vectors CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS concept_exemplars CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS keyword_aliases CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS keyword_concepts CASCADE"))
    
    conn.execute(text("""
        ALTER TABLE run_results
            DROP COLUMN IF EXISTS decision,
            DROP COLUMN IF EXISTS relevance_p,
            DROP COLUMN IF EXISTS relevance_stage,
            DROP COLUMN IF EXISTS relevance_features,
            DROP COLUMN IF EXISTS relevance_reasons,
            DROP COLUMN IF EXISTS concept_id,
            DROP COLUMN IF EXISTS concept_version,
            DROP COLUMN IF EXISTS scorer_version
    """))
    conn.execute(text("""
        ALTER TABLE rejected_candidates
            DROP COLUMN IF EXISTS reason_code,
            DROP COLUMN IF EXISTS relevance_p,
            DROP COLUMN IF EXISTS features
    """))
    conn.execute(text("ALTER TABLE query_runs DROP COLUMN IF EXISTS updated_at"))
