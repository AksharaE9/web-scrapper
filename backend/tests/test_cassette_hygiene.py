"""
tests/test_cassette_hygiene.py — Asserts no sensitive PII in recorded cassettes or fixtures.
"""

from __future__ import annotations

import re
from pathlib import Path


def test_no_real_pii_in_cassettes_and_fixtures() -> None:
    fixtures_dir = Path(__file__).parent / "fixtures"
    if not fixtures_dir.exists():
        return

    # Scan all json, yaml, and txt files
    files = list(fixtures_dir.rglob("*.json")) + list(fixtures_dir.rglob("*.yaml")) + list(fixtures_dir.rglob("*.txt"))

    # Test allowed emails and numbers
    allowed_emails = {"test@example.com", "contact@vinayakapooja.in", "info@lakshmipooja.com"}

    for f in files:
        text = f.read_text(encoding="utf-8")
        # Look for real email addresses
        emails = re.findall(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", text)
        for email in emails:
            if not email.endswith("example.com") and not email.endswith(".local") and email not in allowed_emails:
                assert False, f"Potential real email {email} detected in fixture {f.name}"
