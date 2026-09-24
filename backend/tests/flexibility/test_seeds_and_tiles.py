"""
Tests for Geographic Flexibility, Local Seed Resolution, Snapped Tile Keys, and Cache GC.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from app.graph.nodes.n1_geo import resolve_location
from app.graph.nodes.n3a_overture import _cache_path, _snap_bbox_to_grid, CACHE_GRID_DEG
from app.graph.state import LocationInput
from scripts.cache_gc import prune_cache


@pytest.mark.asyncio
async def test_seed_locality_resolves_fast():
    """Locality listed in seeds/areas.json resolves immediately with >=0.95 confidence."""
    loc = LocationInput(locality="Koramangala", city="Bengaluru", country="India")
    geo = await resolve_location(loc, max_results=100)
    assert geo is not None
    assert geo.geo_confidence >= 0.95
    assert len(geo.centroid) == 2
    assert 77.5 <= geo.centroid[0] <= 77.7
    assert 12.8 <= geo.centroid[1] <= 13.1


@pytest.mark.asyncio
async def test_lat_lon_direct_coordinates_resolves():
    """Direct lat/lon + radius_m resolves directly to a buffered point polygon."""
    loc = LocationInput(
        lat=12.9352,
        lon=77.6245,
        radius_m=3000,
        country="India",
    )
    geo = await resolve_location(loc, max_results=100)
    assert geo is not None
    assert geo.centroid == (77.6245, 12.9352)
    assert geo.buffer_m == 3000
    assert geo.boundary_kind == "buffered_point"
    assert geo.geo_confidence == 1.0


def test_snapped_bbox_tile_reuse():
    """Two nearby coordinates in the same neighbourhood snap to the same grid box."""
    # Point A in Koramangala
    bbox_a = (77.6210, 12.9310, 77.6290, 12.9390)
    # Point B in Koramangala slightly shifted
    bbox_b = (77.6220, 12.9320, 77.6280, 12.9380)

    snapped_a = _snap_bbox_to_grid(bbox_a, grid_deg=CACHE_GRID_DEG)
    snapped_b = _snap_bbox_to_grid(bbox_b, grid_deg=CACHE_GRID_DEG)

    assert snapped_a == snapped_b

    # Cache paths for both are identical
    path_a = _cache_path("2026-09-16.0", snapped_a)
    path_b = _cache_path("2026-09-16.0", snapped_b)
    assert path_a == path_b


def test_cache_gc_pruning(tmp_path: Path):
    """Cache GC deletes parquet and meta files older than cutoff days."""
    release_dir = tmp_path / "2026-08-01.0"
    release_dir.mkdir(parents=True)

    old_parquet = release_dir / "old_tile.parquet"
    old_parquet.touch()
    old_meta = release_dir / "old_tile.meta.json"
    old_meta.write_text(
        json.dumps({
            "release": "2026-08-01.0",
            "written_at": (datetime.now(timezone.utc) - timedelta(days=90)).isoformat(),
            "row_count": 50,
        }),
        encoding="utf-8",
    )

    fresh_parquet = release_dir / "fresh_tile.parquet"
    fresh_parquet.touch()
    fresh_meta = release_dir / "fresh_tile.meta.json"
    fresh_meta.write_text(
        json.dumps({
            "release": "2026-08-01.0",
            "written_at": (datetime.now(timezone.utc) - timedelta(days=5)).isoformat(),
            "row_count": 20,
        }),
        encoding="utf-8",
    )

    with patch("scripts.cache_gc.settings") as mock_settings:
        mock_settings.overture_cache_dir = tmp_path
        res = prune_cache(max_age_days=30, dry_run=False)

        assert res["deleted_files"] == 2
        assert not old_parquet.exists()
        assert not old_meta.exists()
        assert fresh_parquet.exists()
        assert fresh_meta.exists()
