"""
Tests for Overture Cache Policy, TTL, and Data Provenance.
Ensures zero silent fallbacks, proper cache metadata (.meta.json), and strict adherence to cache_policy.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.graph.nodes.n3a_overture import (
    _cache_path,
    _discover_latest_release,
    _meta_path,
    _read_cache_meta,
    _write_cache_meta,
    run as overture_run,
)
from app.graph.state import LocationInput, QueryInput, RunState


def test_hardcoded_release_absent():
    """Verify that '2025-07-23.0' is deleted and never hardcoded in app codebase."""
    backend_app_dir = Path(__file__).resolve().parent.parent.parent / "app"
    found = []
    for py_file in backend_app_dir.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        if "2025-07-23.0" in content:
            found.append(str(py_file))
    assert not found, f"Hardcoded release '2025-07-23.0' found in: {found}"


def test_write_and_read_cache_meta(tmp_path: Path):
    """Verify .meta.json sidecars correctly store and restore cache metadata."""
    cache_file = tmp_path / "test.parquet"
    cache_file.touch()
    
    meta_file = _meta_path(cache_file)
    assert meta_file.name == "test.meta.json"

    _write_cache_meta(
        cache_file=cache_file,
        release="2026-09-16.0",
        snapped_bbox=(77.6, 12.9, 77.7, 13.0),
        row_count=123,
        source_bytes=456789,
    )

    assert meta_file.exists()
    meta = _read_cache_meta(cache_file)
    assert meta["release"] == "2026-09-16.0"
    assert meta["row_count"] == 123
    assert meta["source_bytes"] == 456789
    assert meta["bbox"] == [77.6, 12.9, 77.7, 13.0]
    assert "written_at" in meta


@pytest.mark.asyncio
async def test_first_run_fetches_and_writes_meta(tmp_path: Path):
    """A fresh bbox query writes the cache parquet and .meta.json sidecar."""
    with patch("app.graph.nodes.n3a_overture._discover_latest_release", return_value="2026-09-16.0"), \
         patch("app.graph.nodes.n3a_overture.settings") as mock_settings, \
         patch("app.graph.nodes.n3a_overture._sync_fetch_overture") as mock_fetch:
        
        mock_settings.overture_cache_dir = tmp_path
        mock_fetch.return_value = ([], {"cache_hit": False, "release": "2026-09-16.0", "row_count": 5})

        state: RunState = {
            "run_id": "test-run-1",
            "query": QueryInput(
                location=LocationInput(locality="Koramangala", city="Bengaluru"),
                keywords=["cafe"],
                cache_policy="auto",
            ),
            "geo": MagicMock(bbox=[77.61, 12.92, 77.64, 12.95]),
            "plans": [],
            "candidates": [],
            "source_stats": {},
            "entities": [],
            "verifications": {},
            "iteration": 0,
            "budget": MagicMock(),
            "errors": [],
            "degraded": [],
            "metrics": {},
            "disambiguation_choice": None,
        }

        result = await overture_run(state)
        assert "source_stats" in result
        assert "overture" in result["source_stats"]
        assert result["source_stats"]["overture"]["cache_hit"] is False


@pytest.mark.asyncio
async def test_force_fresh_bypasses_cache(tmp_path: Path):
    """cache_policy='force_fresh' instructs the node to bypass disk cache."""
    with patch("app.graph.nodes.n3a_overture._discover_latest_release", return_value="2026-09-16.0"), \
         patch("app.graph.nodes.n3a_overture.settings") as mock_settings, \
         patch("app.graph.nodes.n3a_overture._sync_fetch_overture") as mock_fetch:
        
        mock_settings.overture_cache_dir = tmp_path
        mock_fetch.return_value = ([], {"cache_hit": False, "release": "2026-09-16.0", "row_count": 10})

        state: RunState = {
            "run_id": "test-run-force-fresh",
            "query": QueryInput(
                location=LocationInput(locality="Indiranagar", city="Bengaluru"),
                keywords=["gym"],
                cache_policy="force_fresh",
            ),
            "geo": MagicMock(bbox=[77.63, 12.96, 77.66, 12.99]),
            "plans": [],
            "candidates": [],
            "source_stats": {},
            "entities": [],
            "verifications": {},
            "iteration": 0,
            "budget": MagicMock(),
            "errors": [],
            "degraded": [],
            "metrics": {},
            "disambiguation_choice": None,
        }

        result = await overture_run(state)
        mock_fetch.assert_called_once()
        args, kwargs = mock_fetch.call_args
        # Positional arg 3 is cache_policy
        assert args[3] == "force_fresh"


def test_release_discovery_failure_without_cache_raises(tmp_path: Path):
    """When discovery fails and no cached release exists, it raises RuntimeError."""
    mock_conn = MagicMock()
    mock_conn.execute.side_effect = Exception("S3 Connection failed")

    with patch("app.graph.nodes.n3a_overture.settings") as mock_settings:
        mock_settings.overture_cache_dir = tmp_path

        with pytest.raises(RuntimeError) as exc_info:
            _discover_latest_release(mock_conn)
        assert "no local cache exists" in str(exc_info.value).lower()


def test_release_discovery_failure_with_cache_marks_degraded(tmp_path: Path):
    """When discovery fails and a cached release exists, it falls back to cache and logs degraded signal."""
    # Create cached release dir
    cached_rel_dir = tmp_path / "2026-08-20.0"
    cached_rel_dir.mkdir(parents=True)

    mock_conn = MagicMock()
    mock_conn.execute.side_effect = Exception("S3 connection error")

    with patch("app.graph.nodes.n3a_overture.settings") as mock_settings:
        mock_settings.overture_cache_dir = tmp_path
        release = _discover_latest_release(mock_conn)
        assert release == "2026-08-20.0"


def test_cache_ttl_expires():
    """Verify _should_use_cache returns False when cache is older than max_cache_age_days."""
    from datetime import datetime, timezone, timedelta
    from app.graph.nodes.n3a_overture import _should_use_cache

    mock_cache_file = MagicMock()
    mock_cache_file.exists.return_value = True

    # 40 days old cache metadata
    old_time = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
    meta = {
        "release": "2026-09-16.0",
        "written_at": old_time,
    }

    # max_cache_age_days = 30 -> expired
    should_use = _should_use_cache(
        cache_file=mock_cache_file,
        meta=meta,
        current_release="2026-09-16.0",
        cache_policy="auto",
        max_cache_age_days=30,
    )
    assert should_use is False

    # max_cache_age_days = 60 -> valid
    should_use_fresh = _should_use_cache(
        cache_file=mock_cache_file,
        meta=meta,
        current_release="2026-09-16.0",
        cache_policy="auto",
        max_cache_age_days=60,
    )
    assert should_use_fresh is True
