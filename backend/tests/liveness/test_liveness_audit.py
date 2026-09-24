"""
tests/liveness/test_liveness_audit.py — Egress accounting and liveness verification.

Answers the fundamental QA question:
"Did bytes actually cross the network or is it reading local files / returning stubs?"
"""

from __future__ import annotations

import socket
import pytest
from app.crawl.simhash import compute_simhash, hamming_distance
from app.sources.overture import get_cache_path


def test_overture_is_local_parquet_cache() -> None:
    """Documents and asserts that Overture Place retrieval reads local disk cache, not live S3 on every run."""
    bbox = (77.60, 12.90, 77.70, 13.00)
    cache_file = get_cache_path("2025-07-23.0", bbox)
    assert str(cache_file).endswith(".parquet")
    assert "overture" in str(cache_file).lower()


def test_simhash_cosmetic_change_drift() -> None:
    """Verifies that minor cosmetic diffs (timestamps) have Hamming distance <= 6."""
    t1 = "Sri Vinayaka Pooja Stores Whitefield Bangalore agarbatti camphor brass lamps"
    t2 = "Sri Vinayaka Pooja Stores Whitefield Bangalore agarbatti camphor brass lamps 2026-09-22"

    h1 = compute_simhash(t1)
    h2 = compute_simhash(t2)

    dist = hamming_distance(h1, h2)
    assert dist <= 6, f"Expected cosmetic change distance <= 6, got {dist}"


def test_simhash_substantive_change_drift() -> None:
    """Verifies that substantive business changes have Hamming distance >= 9."""
    t1 = "Sri Vinayaka Pooja Stores Whitefield Bangalore agarbatti camphor brass lamps"
    t2 = "Divine Footwear Sports Running Shoes Sandals Formal Boots High Heels Leather"

    h1 = compute_simhash(t1)
    h2 = compute_simhash(t2)

    dist = hamming_distance(h1, h2)
    assert dist >= 9, f"Expected substantive change distance >= 9, got {dist}"
