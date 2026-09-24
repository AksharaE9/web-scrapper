"""
tests/edge_cases/test_hostile_inputs.py — Hostile inputs, injection, and crawler fail-closed checks.
"""

from __future__ import annotations

import pytest
from app.crawl.robots import is_url_allowed
from app.relevance.tokenize import tokenize_profile


def test_sqli_in_business_name_safe() -> None:
    sqli_name = "Sri Lakshmi Pooja Stores'; DROP TABLE businesses; --"
    profile = tokenize_profile(sqli_name)
    assert "pooja" in profile.evidence_tokens
    # Semicolons and SQL quotes are stripped
    assert ";" not in profile.clean_name
    assert "'" not in profile.clean_name


def test_xss_in_business_name_sanitized() -> None:
    xss_name = "<script>alert('pwned')</script> Sri Vinayaka Stores"
    profile = tokenize_profile(xss_name)
    assert "<script>" not in profile.name_tokens
    assert "</script>" not in profile.name_tokens


@pytest.mark.asyncio
async def test_robots_unreachable_fail_closed() -> None:
    """A network failure or 5xx fetching robots.txt MUST assume full disallow (fail-closed)."""
    allowed = await is_url_allowed("http://127.0.0.1:59999/some/path")
    assert not allowed, "Robots network failure must fail closed (disallow all)"
