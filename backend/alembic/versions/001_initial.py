"""
Initial migration — LeadCore Zero v2

Creates all extensions, tables, and indexes from Section 8 of the build spec.

IMPORTANT NOTES:
1. Extensions are created before tables.
2. halfvec(384) is used for embeddings. If pgvector < 0.7.0, falls back to vector(384).
   The script checks the installed version and sets @halfvec_supported flag accordingly.
3. Always run against DATABASE_URL_DIRECT (non-pooled), not the pooled URL.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


# ── Helper: detect halfvec support ───────────────────────────────────────────

def _check_halfvec_support(conn: sa.Connection) -> bool:
    """Return True if installed pgvector supports halfvec (>= 0.7.0)."""
    result = conn.execute(
        text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
    ).fetchone()
    if result is None:
        return False
    version = result[0]  # e.g. "0.8.0"
    parts = [int(x) for x in version.split(".")]
    return (parts[0], parts[1]) >= (0, 7)


def upgrade() -> None:
    conn = op.get_bind()

    # ── Extensions ────────────────────────────────────────────────────────
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS citext"))

    halfvec_ok = _check_halfvec_support(conn)
    vec_type = "halfvec(384)" if halfvec_ok else "vector(384)"
    print(f"\n  pgvector halfvec support: {halfvec_ok} → using {vec_type}\n")

    # ── query_runs ────────────────────────────────────────────────────────
    op.create_table(
        "query_runs",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=text("gen_random_uuid()")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=text("NOW()"), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="queued"),
        # status: queued|running|needs_input|completed|partial|failed|failed_no_sources|cancelled
        sa.Column("raw_input", sa.JSON(), nullable=True),
        sa.Column("locality", sa.Text(), nullable=True),
        sa.Column("city", sa.Text(), nullable=True),
        sa.Column("state", sa.Text(), nullable=True),
        sa.Column("country", sa.Text(), nullable=False, server_default="India"),
        sa.Column("keywords", sa.ARRAY(sa.Text()), nullable=True),
        sa.Column("exclude_keywords", sa.ARRAY(sa.Text()), nullable=True),
        sa.Column("geo_display_name", sa.Text(), nullable=True),
        sa.Column("boundary_kind", sa.Text(), nullable=True),
        sa.Column("geo_confidence", sa.Float(), nullable=True),
        sa.Column("source_versions", sa.JSON(), nullable=True),
        sa.Column("options", sa.JSON(), nullable=True),
        sa.Column("stats", sa.JSON(), nullable=True),
        sa.Column("graph_version", sa.Text(), nullable=True),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("batch_id", sa.UUID(), nullable=True),
    )
    # Add PostGIS geometry column for boundary
    conn.execute(text(
        "ALTER TABLE query_runs ADD COLUMN boundary geography(MultiPolygon, 4326)"
    ))

    op.create_index("ix_query_runs_created_at", "query_runs", [sa.text("created_at DESC")])
    op.create_index("ix_query_runs_status", "query_runs", ["status"])
    op.create_index("ix_query_runs_batch_id", "query_runs", ["batch_id"])

    # ── businesses ────────────────────────────────────────────────────────
    conn.execute(text("""
        CREATE TABLE businesses (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            canonical_name TEXT NOT NULL,
            name_norm TEXT NOT NULL,
            primary_category TEXT,
            categories TEXT[],
            phones_e164 TEXT[],
            emails CITEXT[],
            website_domain TEXT,
            website_url TEXT,
            socials JSONB,
            address JSONB,
            address_text TEXT,
            locality TEXT,
            city TEXT,
            state TEXT,
            country TEXT DEFAULT 'India',
            geohash7 TEXT,
            operating_status TEXT,
            confidence REAL,
            tier TEXT,
            independent_source_count SMALLINT DEFAULT 0,
            first_seen_at TIMESTAMPTZ DEFAULT NOW(),
            last_verified_at TIMESTAMPTZ,
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """))
    # PostGIS and pgvector columns added separately for type flexibility
    conn.execute(text(
        "ALTER TABLE businesses ADD COLUMN geom geography(Point, 4326)"
    ))
    conn.execute(text(
        f"ALTER TABLE businesses ADD COLUMN embedding {vec_type}"
    ))

    # Indexes for businesses
    conn.execute(text("CREATE INDEX ix_businesses_geom ON businesses USING GIST(geom)"))
    conn.execute(text(
        "CREATE INDEX ix_businesses_name_trgm ON businesses USING GIN(name_norm gin_trgm_ops)"
    ))
    conn.execute(text("CREATE INDEX ix_businesses_phones ON businesses USING GIN(phones_e164)"))
    conn.execute(text("CREATE INDEX ix_businesses_emails ON businesses USING GIN(emails)"))
    op.create_index("ix_businesses_website_domain", "businesses", ["website_domain"])
    op.create_index("ix_businesses_geohash7", "businesses", ["geohash7"])
    conn.execute(text(
        f"CREATE INDEX ix_businesses_embedding ON businesses USING HNSW(embedding "
        f"{'halfvec_cosine_ops' if halfvec_ok else 'vector_cosine_ops'})"
    ))

    # ── business_sources ──────────────────────────────────────────────────
    op.create_table(
        "business_sources",
        sa.Column("business_id", sa.UUID(), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("source_record_id", sa.Text(), nullable=False),
        sa.Column("lineage", sa.ARRAY(sa.Text()), nullable=True),
        sa.Column("licence", sa.Text(), nullable=True),
        sa.Column("raw", sa.JSON(), nullable=True),
        sa.Column("fetched_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.UniqueConstraint("source", "source_record_id", name="uq_business_sources_source_id"),
    )
    op.create_index("ix_business_sources_business_id", "business_sources", ["business_id"])

    # ── field_provenance ──────────────────────────────────────────────────
    op.create_table(
        "field_provenance",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("business_id", sa.UUID(), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("field", sa.Text(), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("evidence_url", sa.Text(), nullable=True),
        sa.Column("evidence_quote", sa.Text(), nullable=True),
        sa.Column("extracted_by", sa.Text(), nullable=True),  # deterministic|jsonld|llm
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("is_selected", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("observed_at", sa.TIMESTAMP(timezone=True), server_default=text("NOW()")),
    )
    op.create_index("ix_field_provenance_business_field", "field_provenance", ["business_id", "field"])

    # ── run_results ───────────────────────────────────────────────────────
    op.create_table(
        "run_results",
        sa.Column("run_id", sa.UUID(), sa.ForeignKey("query_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("business_id", sa.UUID(), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("keyword", sa.Text(), nullable=False),
        sa.Column("match_score", sa.Float(), nullable=True),
        sa.Column("match_reason", sa.Text(), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("is_new_business", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("edge_case", sa.Boolean(), nullable=False, server_default="false"),
        sa.PrimaryKeyConstraint("run_id", "business_id", "keyword"),
    )
    op.create_index("ix_run_results_run_rank", "run_results", ["run_id", "rank"])

    # ── rejected_candidates ───────────────────────────────────────────────
    conn.execute(text("""
        CREATE TABLE rejected_candidates (
            run_id UUID REFERENCES query_runs(id) ON DELETE CASCADE,
            source TEXT,
            source_record_id TEXT,
            name TEXT,
            reason TEXT,
            geom geography(Point, 4326)
        )
    """))
    op.create_index("ix_rejected_candidates_run_id", "rejected_candidates", ["run_id"])

    # ── possible_duplicates ───────────────────────────────────────────────
    op.create_table(
        "possible_duplicates",
        sa.Column("run_id", sa.UUID(), sa.ForeignKey("query_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("business_a", sa.UUID(), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("business_b", sa.UUID(), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("match_probability", sa.Float(), nullable=False),
        sa.Column("resolution", sa.Text(), nullable=True),
    )

    # ── verifications ─────────────────────────────────────────────────────
    conn.execute(text("""
        CREATE TABLE verifications (
            business_id UUID REFERENCES businesses(id) ON DELETE CASCADE,
            check_name TEXT NOT NULL,
            outcome TEXT NOT NULL,  -- passed|failed|inconclusive
            detail JSONB,
            checked_at TIMESTAMPTZ DEFAULT NOW(),
            PRIMARY KEY (business_id, check_name)
        )
    """))

    # ── crawl_log ─────────────────────────────────────────────────────────
    op.create_table(
        "crawl_log",
        sa.Column("domain", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("outcome", sa.Text(), nullable=True),
        sa.Column("robots_allowed", sa.Boolean(), nullable=True),
        sa.Column("fetched_at", sa.TIMESTAMP(timezone=True), server_default=text("NOW()")),
    )
    op.create_index("ix_crawl_log_domain", "crawl_log", ["domain"])

    # ── doc_chunks ────────────────────────────────────────────────────────
    conn.execute(text(f"""
        CREATE TABLE doc_chunks (
            id BIGSERIAL PRIMARY KEY,
            business_id UUID REFERENCES businesses(id) ON DELETE CASCADE,
            url TEXT,
            chunk TEXT,
            embedding {vec_type},
            fetched_at TIMESTAMPTZ DEFAULT NOW()
        )
    """))
    conn.execute(text(
        f"CREATE INDEX ix_doc_chunks_embedding ON doc_chunks USING HNSW(embedding "
        f"{'halfvec_cosine_ops' if halfvec_ok else 'vector_cosine_ops'})"
    ))
    op.create_index("ix_doc_chunks_business_id", "doc_chunks", ["business_id"])

    # ── taxonomy_vectors ──────────────────────────────────────────────────
    conn.execute(text(f"""
        CREATE TABLE taxonomy_vectors (
            id TEXT PRIMARY KEY,
            system TEXT NOT NULL,  -- overture|osm
            label TEXT NOT NULL,
            path TEXT,
            embedding {vec_type}
        )
    """))
    conn.execute(text(
        f"CREATE INDEX ix_taxonomy_vectors_embedding ON taxonomy_vectors USING HNSW(embedding "
        f"{'halfvec_cosine_ops' if halfvec_ok else 'vector_cosine_ops'})"
    ))

    # ── keyword_plans ─────────────────────────────────────────────────────
    conn.execute(text(f"""
        CREATE TABLE keyword_plans (
            keyword_norm TEXT PRIMARY KEY,
            plan JSONB NOT NULL,
            embedding {vec_type},
            uses INT DEFAULT 1,
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """))
    conn.execute(text(
        f"CREATE INDEX ix_keyword_plans_embedding ON keyword_plans USING HNSW(embedding "
        f"{'halfvec_cosine_ops' if halfvec_ok else 'vector_cosine_ops'})"
    ))

    # ── geo_cache ─────────────────────────────────────────────────────────
    op.create_table(
        "geo_cache",
        sa.Column("query_hash", sa.Text(), primary_key=True),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("response", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=text("NOW()")),
    )

    # ── area_seeds ────────────────────────────────────────────────────────
    op.create_table(
        "area_seeds",
        sa.Column("city", sa.Text(), nullable=False),
        sa.Column("region", sa.Text(), nullable=False),
        sa.Column("area", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("city", "region", "area"),
    )
    op.create_index("ix_area_seeds_city", "area_seeds", ["city"])
    conn.execute(text(
        "CREATE INDEX ix_area_seeds_area_trgm ON area_seeds USING GIN(area gin_trgm_ops)"
    ))

    # ── keyword_presets ───────────────────────────────────────────────────
    op.create_table(
        "keyword_presets",
        sa.Column("name", sa.Text(), primary_key=True),
        sa.Column("search_categories", sa.ARRAY(sa.Text()), nullable=False),
        sa.Column("exclude_keywords", sa.ARRAY(sa.Text()), nullable=True),
    )

    # ── gold_labels ───────────────────────────────────────────────────────
    op.create_table(
        "gold_labels",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.UUID(), sa.ForeignKey("query_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("business_id", sa.UUID(), sa.ForeignKey("businesses.id", ondelete="SET NULL"), nullable=True),
        sa.Column("rejected_ref", sa.JSON(), nullable=True),
        sa.Column("label_type", sa.Text(), nullable=False),  # lead|field|duplicate
        sa.Column("field", sa.Text(), nullable=True),
        sa.Column("verdict", sa.Text(), nullable=False),  # valid|invalid|correct|wrong|cant_tell
        sa.Column("labeler", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=text("NOW()")),
    )
    op.create_index("ix_gold_labels_run_id", "gold_labels", ["run_id"])
    op.create_index("ix_gold_labels_business_id", "gold_labels", ["business_id"])

    # ── missed_businesses ─────────────────────────────────────────────────
    conn.execute(text("""
        CREATE TABLE missed_businesses (
            id BIGSERIAL PRIMARY KEY,
            run_id UUID REFERENCES query_runs(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            note TEXT,
            geom geography(Point, 4326),
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """))

    # ── metrics_snapshots ─────────────────────────────────────────────────
    op.create_table(
        "metrics_snapshots",
        sa.Column("run_id", sa.UUID(), sa.ForeignKey("query_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("metric", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),  # ground_truth|proxy
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("ci_low", sa.Float(), nullable=True),
        sa.Column("ci_high", sa.Float(), nullable=True),
        sa.Column("n", sa.Integer(), nullable=True),
        sa.Column("computed_at", sa.TIMESTAMP(timezone=True), server_default=text("NOW()")),
    )
    op.create_index("ix_metrics_snapshots_run_id", "metrics_snapshots", ["run_id"])

    # ── scoring_models ────────────────────────────────────────────────────
    op.create_table(
        "scoring_models",
        sa.Column("version", sa.Text(), primary_key=True),
        sa.Column("params", sa.JSON(), nullable=False),
        sa.Column("trained_on", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=text("NOW()")),
    )

    # ── delivered_leads ───────────────────────────────────────────────────
    op.create_table(
        "delivered_leads",
        sa.Column("business_id", sa.UUID(), sa.ForeignKey("businesses.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("delivered_at", sa.TIMESTAMP(timezone=True), server_default=text("NOW()")),
        sa.Column("channel", sa.Text(), nullable=True),
        sa.Column("batch_ref", sa.Text(), nullable=True),
    )

    # ── suppression_list ──────────────────────────────────────────────────
    op.create_table(
        "suppression_list",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("phone_e164", sa.Text(), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("domain", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=text("NOW()")),
    )


def downgrade() -> None:
    conn = op.get_bind()
    tables = [
        "suppression_list", "delivered_leads", "scoring_models",
        "metrics_snapshots", "missed_businesses", "gold_labels",
        "keyword_presets", "area_seeds", "geo_cache", "keyword_plans",
        "taxonomy_vectors", "doc_chunks", "crawl_log", "verifications",
        "possible_duplicates", "rejected_candidates", "run_results",
        "field_provenance", "business_sources", "businesses", "query_runs",
    ]
    for table in tables:
        conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
    conn.execute(text("DROP EXTENSION IF EXISTS vector CASCADE"))
    conn.execute(text("DROP EXTENSION IF EXISTS pg_trgm CASCADE"))
    conn.execute(text("DROP EXTENSION IF EXISTS postgis CASCADE"))
    conn.execute(text("DROP EXTENSION IF EXISTS citext CASCADE"))
