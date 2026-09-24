"""
LeadCore Zero v2 — Centralized Geospatial SQL Helpers

Standardizes GeoJSON coordinate convention:
  - Longitude first (X), Latitude second (Y)
  - PostGIS geography(Point, 4326) geometry helpers
"""

from __future__ import annotations

# SQL expressions for point creation and coordinate extraction
ST_MAKE_POINT_EXPR = "ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography"
ST_MAKE_POINT_NAMED = "ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)::geography"

ST_LON_EXTRACT_EXPR = "ST_X(geom::geometry) AS lon"
ST_LAT_EXTRACT_EXPR = "ST_Y(geom::geometry) AS lat"
ST_COORDS_SELECT = "ST_X(geom::geometry) AS lon, ST_Y(geom::geometry) AS lat"


def point_geography_sql(lon_param: str = "%s", lat_param: str = "%s") -> str:
    """Return parameterized SQL expression to construct a 4326 geography Point (lon first)."""
    return f"ST_SetSRID(ST_MakePoint({lon_param}, {lat_param}), 4326)::geography"


def select_geom_coords_sql(geom_col: str = "geom") -> str:
    """Return SQL fragment to select longitude and latitude from a geography/geometry column."""
    return f"ST_X({geom_col}::geometry) AS lon, ST_Y({geom_col}::geometry) AS lat"
