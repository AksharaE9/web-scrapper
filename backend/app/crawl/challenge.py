"""
app/crawl/challenge.py — Bot challenge and CAPTCHA detection.

Doctrine:
Detect Cloudflare / Turnstile / PerimeterX / reCAPTCHA challenges,
mark domain 'blocked_by_site', and immediately move on. No bypass attempts.
"""

from __future__ import annotations

import re


CHALLENGE_PATTERNS = [
    re.compile(r"cf-browser-verification", re.IGNORECASE),
    re.compile(r"cloudflare-challenge", re.IGNORECASE),
    re.compile(r"just a moment\.\.\.", re.IGNORECASE),
    re.compile(r"turnstile", re.IGNORECASE),
    re.compile(r"g-recaptcha", re.IGNORECASE),
    re.compile(r"hcaptcha", re.IGNORECASE),
    re.compile(r"security check to access", re.IGNORECASE),
    re.compile(r"bot detection", re.IGNORECASE),
]


def is_bot_challenge(html: str, status_code: int) -> bool:
    """Detect if a page is a Cloudflare or bot challenge page."""
    if status_code in (403, 503, 429):
        for pat in CHALLENGE_PATTERNS:
            if pat.search(html[:3000]):
                return True

    # Check title / body in 200 responses with challenge text
    if any(pat.search(html[:1500]) for pat in CHALLENGE_PATTERNS[:4]):
        return True

    return False
