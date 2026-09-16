"""
Unit tests for Geo Resolution & Coordinate Conventions (GeoJSON lon/lat order)
"""

import pytest
from app.graph.state import GeoResolution


def test_koramangala_centroid() -> None:
    """Enforce GeoJSON convention: (longitude, latitude) order."""
    # Koramangala centroid is ~ lon 77.62, lat 12.93
    res = GeoResolution(
        display_name="Koramangala, Bengaluru, Karnataka, India",
        polygon_wkt="POLYGON((77.60 12.92, 77.64 12.92, 77.64 12.95, 77.60 12.95, 77.60 12.92))",
        boundary_kind="admin_polygon",
        bbox=(77.60, 12.92, 77.64, 12.95),  # min_lon, min_lat, max_lon, max_lat
        centroid=(77.6245, 12.9352),         # lon, lat
        geo_confidence=0.95,
    )

    lon, lat = res.centroid
    assert 77.0 <= lon <= 78.0, f"Longitude swapped or incorrect: {lon}"
    assert 12.0 <= lat <= 13.5, f"Latitude swapped or incorrect: {lat}"

    min_lon, min_lat, max_lon, max_lat = res.bbox
    assert min_lon < max_lon
    assert min_lat < max_lat
    assert 77.0 <= min_lon <= 78.0
    assert 12.0 <= min_lat <= 13.5


def test_swapped_coordinates_rejected() -> None:
    """Verify that inverted bbox coordinates raise validation errors."""
    with pytest.raises((AssertionError, ValueError)):
        # min_lat passed as min_lon, etc.
        GeoResolution(
            display_name="Invalid BBox",
            polygon_wkt="POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))",
            boundary_kind="admin_polygon",
            bbox=(77.64, 12.92, 77.60, 12.95),  # min_lon > max_lon
            centroid=(77.62, 12.93),
            geo_confidence=0.5,
        )
