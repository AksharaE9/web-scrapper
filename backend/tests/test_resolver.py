"""
Unit tests for Entity Resolution and Field Provenance Selection
"""

from app.graph.state import RawCandidate
from app.resolve.golden_record import build_golden_record
from app.resolve.normalize import normalise_domain, normalise_phone


def test_normalise_phone() -> None:
    assert normalise_phone("+91 98765 43210") == "+919876543210"
    assert normalise_phone("09876543210") == "+919876543210"
    assert normalise_phone("9876543210") == "+919876543210"


def test_normalise_domain() -> None:
    assert normalise_domain("https://www.cult.fit/gyms/koramangala") == "cult.fit"
    assert normalise_domain("http://goldsgym.in/index.html") == "goldsgym.in"


def test_golden_record_merge() -> None:
    cand1 = RawCandidate(
        source="overture",
        source_record_id="ov_1",
        name="Gold's Gym Koramangala",
        lon=77.6245,
        lat=12.9352,
        categories=["gym", "fitness_center"],
        phones=["+919876543210"],
        websites=["https://goldsgym.in"],
        source_confidence=0.9,
    )
    cand2 = RawCandidate(
        source="osm",
        source_record_id="node/12345",
        name="Golds Gym",
        lon=77.6246,
        lat=12.9353,
        categories=["leisure=fitness_centre"],
        phones=["09876543210"],
        websites=[],
        source_confidence=0.8,
    )

    golden = build_golden_record("test_cluster_1", [cand1, cand2])
    assert "Gold" in golden.canonical_name
    assert "+919876543210" in golden.phones_e164
    assert golden.website_domain == "goldsgym.in"
    assert len(golden.source_ids) == 2
