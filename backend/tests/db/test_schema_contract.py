"""
A3 Regression Test — Schema Contract Verification
Verifies that required table columns (e.g. query_runs.updated_at, run_results.decision, etc.)
exist in the database schema contract.
"""

import pytest
from app.db import pool as db_pool

EXPECTED_COLUMNS = {
    "query_runs": {"id", "created_at", "status", "locality", "city", "state", "country", "keywords", "updated_at"},
    "businesses": {"id", "canonical_name", "name_norm", "primary_category", "categories", "phones_e164", "emails", "website_domain", "geom", "confidence", "tier", "updated_at"},
    "run_results": {"run_id", "business_id", "keyword", "match_score", "decision", "relevance_p", "relevance_stage", "relevance_features", "relevance_reasons", "concept_id", "concept_version"},
    "rejected_candidates": {"run_id", "source", "source_record_id", "name", "reason", "reason_code", "relevance_p", "features"},
    "keyword_concepts": {"concept_id", "version", "keyword_norm", "card", "embedding", "origin"},
    "concept_exemplars": {"id", "concept_id", "polarity", "text", "embedding", "origin"},
    "llm_cache": {"key", "model", "response", "created_at"},
}

@pytest.mark.asyncio
async def test_schema_contract_columns() -> None:
    async with db_pool.get_conn() as conn:
        for table_name, expected_cols in EXPECTED_COLUMNS.items():
            cursor = await conn.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
                (table_name,),
            )
            rows = await cursor.fetchall()
            actual_cols = {r["column_name"] for r in rows} if rows and isinstance(rows[0], dict) else {r[0] for r in rows}
            
            missing = expected_cols - actual_cols
            assert not missing, f"Table '{table_name}' is missing expected columns: {missing}. Actual columns: {actual_cols}"

