"""
tests/compliance/test_compliance_audit.py — Strict source and protocol compliance validation.
"""

from __future__ import annotations

import re
from pathlib import Path


def test_no_forbidden_scraping_targets() -> None:
    """Scan all app/ files to ensure no references to Google Maps scraping or residential proxy rotators."""
    backend_app = Path(__file__).resolve().parent.parent.parent / "app"
    py_files = list(backend_app.rglob("*.py"))

    forbidden_patterns = [
        r"google\.com/maps",
        r"2captcha",
        r"anticaptcha",
        r"deathbycaptcha",
        r"residential_proxy",
    ]

    for f in py_files:
        content = f.read_text(encoding="utf-8").lower()
        for pat in forbidden_patterns:
            matches = re.findall(pat, content)
            assert not matches, f"Forbidden scraping pattern '{pat}' found in {f.name}"


def test_identifying_user_agent_format() -> None:
    """Crawler User-Agent must contain project identifier and contact email."""
    from app.settings import settings
    ua = settings.crawler_user_agent
    assert "LeadCoreZero" in ua
    assert "contact:" in ua
    assert "@" in ua
