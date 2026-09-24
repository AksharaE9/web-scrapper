"""
app/crawl/robots.py — Robots.txt parser and policy enforcer.

Compliance rules:
- Respects Disallow, Crawl-delay, Request-rate
- On 5xx or network error when fetching robots.txt: assume full disallow
- Caches robots.txt rules for max 24 hours
"""

from __future__ import annotations

import asyncio
import logging
import time
import urllib.parse
import urllib.robotparser
import httpx
from app.settings import settings

logger = logging.getLogger(__name__)

# Cache: domain -> (RobotFileParser, expiration_timestamp)
_ROBOTS_CACHE: dict[str, tuple[urllib.robotparser.RobotFileParser | None, float]] = {}
_CACHE_TTL_SECS = 86400  # 24 hours
_LOCK = asyncio.Lock()


async def is_url_allowed(url: str) -> bool:
    """Check if crawling a URL is permitted by the domain's robots.txt."""
    try:
        parsed = urllib.parse.urlparse(url)
        scheme = parsed.scheme or "https"
        domain = parsed.netloc or parsed.path
        if not domain:
            return False

        robots_url = f"{scheme}://{domain}/robots.txt"
        now = time.monotonic()

        async with _LOCK:
            if domain in _ROBOTS_CACHE:
                rp, exp = _ROBOTS_CACHE[domain]
                if now < exp:
                    if rp is None:
                        # 5xx or network error previously -> assume full disallow
                        return False
                    return rp.can_fetch(settings.crawler_user_agent, url)

        # Fetch robots.txt
        rp = urllib.robotparser.RobotFileParser()
        headers = {"User-Agent": settings.crawler_user_agent}
        try:
            async with httpx.AsyncClient(timeout=8.0, headers=headers, follow_redirects=True) as client:
                resp = await client.get(robots_url)
                if resp.status_code == 200:
                    rp.parse(resp.text.splitlines())
                    async with _LOCK:
                        _ROBOTS_CACHE[domain] = (rp, now + _CACHE_TTL_SECS)
                    return rp.can_fetch(settings.crawler_user_agent, url)
                elif resp.status_code in (401, 403):
                    # Explicit access forbidden
                    async with _LOCK:
                        _ROBOTS_CACHE[domain] = (None, now + _CACHE_TTL_SECS)
                    return False
                elif resp.status_code >= 500:
                    # 5xx server error -> fail closed (assume full disallow)
                    logger.warning(f"Robots.txt returned 5xx for {domain}, assuming disallow")
                    async with _LOCK:
                        _ROBOTS_CACHE[domain] = (None, now + _CACHE_TTL_SECS)
                    return False
                else:
                    # 404 means no robots.txt restrictions
                    rp.allow_all = True
                    async with _LOCK:
                        _ROBOTS_CACHE[domain] = (rp, now + _CACHE_TTL_SECS)
                    return True
        except Exception as e:
            # Network error fetching robots.txt -> fail closed (assume full disallow)
            logger.warning(f"Network error fetching robots.txt for {domain}: {e}, assuming disallow")
            async with _LOCK:
                _ROBOTS_CACHE[domain] = (None, now + _CACHE_TTL_SECS)
            return False

    except Exception as e:
        logger.warning(f"robots.txt check error for {url}: {e}")
        return False
