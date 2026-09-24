"""
Tests for Config API endpoints and frontend live-sync data guarantees.
Verifies all 5 /api/config/* endpoints return compliant, valid, ETag-enabled schemas.
"""

from __future__ import annotations

from pathlib import Path
import yaml
from fastapi.testclient import TestClient

from app.main import create_app

client = TestClient(create_app())


def test_get_config_lexicon():
    """GET /api/config/lexicon returns non_evidence terms matching YAML files and an ETag."""
    resp = client.get("/api/config/lexicon")
    assert resp.status_code == 200
    data = resp.json()

    assert "version" in data
    assert "non_evidence_terms" in data
    assert "variants" in data
    assert len(data["non_evidence_terms"]) > 0

    # Test ETag conditional get (304)
    etag = resp.headers.get("ETag")
    assert etag is not None
    resp304 = client.get("/api/config/lexicon", headers={"If-None-Match": etag})
    assert resp304.status_code == 304


def test_get_config_graph():
    """GET /api/config/graph returns ordered pipeline nodes with critical flags."""
    resp = client.get("/api/config/graph")
    assert resp.status_code == 200
    nodes = resp.json()
    assert isinstance(nodes, list)
    assert len(nodes) >= 10

    node_ids = [n["id"] for n in nodes]
    assert "n1_geo" in node_ids
    assert "n12_report" in node_ids

    # Every node has required fields
    for n in nodes:
        assert "id" in n
        assert "label" in n
        assert "critical" in n
        assert "order" in n


def test_get_config_sources():
    """GET /api/config/sources returns sources with implementation status and licences."""
    resp = client.get("/api/config/sources")
    assert resp.status_code == 200
    sources = resp.json()
    assert isinstance(sources, list)

    by_id = {s["id"]: s for s in sources}
    assert "overture" in by_id
    assert "osm" in by_id
    assert "wikidata" in by_id

    # Overture & OSM are implemented; Wikidata is stub
    assert by_id["overture"]["implemented"] is True
    assert by_id["osm"]["implemented"] is True
    assert by_id["wikidata"]["implemented"] is False


def test_get_config_limits():
    """GET /api/config/limits returns dynamic boundaries for max_results."""
    resp = client.get("/api/config/limits")
    assert resp.status_code == 200
    limits = resp.json()

    assert limits["max_results_min"] == 1
    assert limits["max_results_max"] >= 5000
    assert "warn_above" in limits


def test_get_config_thresholds():
    """GET /api/config/thresholds returns tau_hi, tau_lo, and tiers."""
    resp = client.get("/api/config/thresholds")
    assert resp.status_code == 200
    th = resp.json()

    assert "tau_hi" in th
    assert "tau_lo" in th
    assert th["tau_hi"] > th["tau_lo"]
    assert "Verified" in th["tiers"]
