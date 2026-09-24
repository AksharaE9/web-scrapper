"""
A6 Regression Test — BoundaryKind Type Safety & Static Audit
Asserts that GeoResolution validates boundary_kind correctly for all paths,
and statically audits app/ codebase for unapproved boundary_kind literals.
"""

import re
from pathlib import Path
import pytest
from app.graph.state import GeoResolution, BoundaryKind

VALID_KINDS: set[BoundaryKind] = {"admin_polygon", "division_polygon", "buffered_point"}

def test_geo_resolution_valid_boundary_kinds() -> None:
    for kind in VALID_KINDS:
        geo = GeoResolution(
            display_name=f"Test {kind}",
            polygon_wkt="POLYGON((77.60 12.92, 77.64 12.92, 77.64 12.95, 77.60 12.95, 77.60 12.92))",
            boundary_kind=kind,
            bbox=(77.60, 12.92, 77.64, 12.95),
            centroid=(77.62, 12.93),
            geo_confidence=0.9,
        )
        assert geo.boundary_kind == kind

def test_geo_resolution_invalid_boundary_kind_rejected() -> None:
    with pytest.raises((ValueError, AssertionError)):
        GeoResolution(
            display_name="Invalid Kind",
            polygon_wkt="POLYGON((77.60 12.92, 77.64 12.92, 77.64 12.95, 77.60 12.95, 77.60 12.92))",
            boundary_kind="fallback_point",  # type: ignore
            bbox=(77.60, 12.92, 77.64, 12.95),
            centroid=(77.62, 12.93),
            geo_confidence=0.5,
        )

def test_static_grep_for_boundary_kind_literals() -> None:
    """Statically verify that no unapproved boundary_kind literals exist in app/."""
    app_dir = Path(__file__).resolve().parent.parent.parent / "app"
    forbidden_literals = ["fallback_point", "seed_polygon", "point_buffer"]
    
    violations: list[str] = []
    for py_file in app_dir.rglob("*.py"):
        if py_file.name == "state.py":
            continue
        content = py_file.read_text(encoding="utf-8")
        for bad in forbidden_literals:
            if re.search(rf'["\']{bad}["\']', content):
                violations.append(f"{py_file.name}: found forbidden literal '{bad}'")
                
    assert not violations, f"Found unapproved boundary kind literals in codebase: {violations}"
