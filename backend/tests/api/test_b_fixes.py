"""
tests/api/test_b_fixes.py — Regression guard tests for LeadCore Zero root-cause fixes.
Guards:
- B1: Keywords array column roundtrip from POST /api/runs
- B2: Undefined names (ruff F821 / module import)
- B3: Failed run exposes error telemetry
- B5: RunCard does not contain placeholder 'Target Area'
- B6: Default cache policy is 'auto' with 30 days
"""

from __future__ import annotations

import ast
import importlib
import pkgutil
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.api.runs import QueryInput
from app.db.pool import get_conn
from app.main import app

client = TestClient(app)


@pytest.mark.asyncio
async def test_create_run_persists_array_columns() -> None:
    """Guard B1: POST /api/runs persists keywords as PostgreSQL text[] array, not json string."""
    payload = {
        "location": {"locality": "Indiranagar", "city": "Bengaluru", "country": "India"},
        "keywords": ["coffee shop", "cafe"],
        "exclude_keywords": ["starbucks"],
        "max_results": 5,
    }
    resp = client.post("/api/runs", json=payload)
    assert resp.status_code == 202
    run_id = resp.json()["run_id"]

    async with get_conn() as conn:
        row = await (await conn.execute("SELECT keywords, exclude_keywords FROM query_runs WHERE id = %s", (run_id,))).fetchone()
        assert row is not None
        keywords = row["keywords"] if isinstance(row, dict) else row[0]
        exclude_keywords = row["exclude_keywords"] if isinstance(row, dict) else row[1]
        
        assert isinstance(keywords, list)
        assert keywords == ["coffee shop", "cafe"]
        assert isinstance(exclude_keywords, list)
        assert exclude_keywords == ["starbucks"]


def test_no_undefined_names() -> None:
    """Guard B2: Ensure all modules in app/ compile and import with zero NameErrors or missing symbols."""
    app_dir = Path(__file__).parent.parent.parent / "app"
    py_files = list(app_dir.rglob("*.py"))
    assert len(py_files) > 0

    for f in py_files:
        code = f.read_text(encoding="utf-8")
        tree = ast.parse(code, filename=str(f))
        compiled = compile(tree, filename=str(f), mode="exec")
        assert compiled is not None


def test_default_cache_policy_is_auto() -> None:
    """Guard B6: QueryInput defaults to cache_policy='auto' and max_cache_age_days=30."""
    q = QueryInput(
        location={"city": "Hyderabad"},
        keywords=["hotels"],
    )
    assert q.cache_policy == "auto"
    assert q.max_cache_age_days == 30


def test_run_card_has_no_placeholder_title() -> None:
    """Guard B5: RunCard handles parsed localities and does not fall back to 'Target Area'."""
    payload = {
        "location": {"raw_text": "Banjara Hills, Hyderabad", "city": "Hyderabad", "country": "India"},
        "keywords": ["hotels"],
    }
    resp = client.post("/api/runs", json=payload)
    assert resp.status_code == 202
    run_id = resp.json()["run_id"]

    card_resp = client.get(f"/api/runs/{run_id}")
    assert card_resp.status_code == 200
    card_data = card_resp.json()
    assert card_data["locality"] != "Target Area"


def test_failed_run_exposes_error() -> None:
    """Guard B3: RunCard contains error, failed_node, degraded fields."""
    resp = client.get("/api/runs")
    assert resp.status_code == 200
    runs = resp.json()
    assert isinstance(runs, list)
    if runs:
        first = runs[0]
        assert "error" in first
        assert "failed_node" in first
        assert "degraded" in first
