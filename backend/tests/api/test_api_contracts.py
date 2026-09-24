"""
tests/api/test_api_contracts.py — API contract tests for all FastAPI endpoints.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_api_health_endpoint() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "neon" in data
    assert "overture" in data
    assert "nominatim" in data
    assert "ollama" in data


def test_api_presets_endpoint() -> None:
    response = client.get("/api/presets")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_api_concepts_endpoint() -> None:
    response = client.get("/api/concepts/pooja_store")
    assert response.status_code == 200
    data = response.json()
    assert data["concept_id"] == "pooja_store"
    assert "signals" in data
    assert "categories" in data


def test_api_runs_validation_failure() -> None:
    # Empty body must return 422 Unprocessable Entity
    response = client.post("/api/runs", json={})
    assert response.status_code == 422
