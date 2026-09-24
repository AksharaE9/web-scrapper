"""
app/crawl/fetcher.py — Scrapling Fetcher with Chrome TLS fingerprinting and size caps.
"""

from __future__ import annotations

import logging
from typing import Any
import httpx
from app.crawl.challenge import is_bot_challenge
from app.crawl.simhash import compute_simhash
from app.settings import settings

logger = logging.getLogger(__name__)

MAX_HTML_BYTES = 2 * 1024 * 1024  # 2 MB response size cap


class FetchResult:
    def __init__(
        self,
        url: str,
        status_code: int,
        html: str,
        outcome: str,
        simhash: int,
        etag: str | None = None,
        last_modified: str | None = None,
    ) -> None:
        self.url = url
        self.status_code = status_code
        self.html = html
        self.outcome = outcome  # ok | blocked_by_site | error | disallow | 304_not_modified
        self.simhash = simhash
        self.etag = etag
        self.last_modified = last_modified


import ipaddress
import socket
from urllib.parse import urlparse

def _is_ssrf_safe(url: str) -> bool:
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = parsed.hostname
        if not hostname or hostname in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
            return False
        
        # Check cloud metadata endpoints
        if hostname == "169.254.169.254" or hostname.endswith(".internal"):
            return False

        # Attempt IP parse
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return False
        except ValueError:
            pass  # Standard domain name
        return True
    except Exception:
        return False


async def fetch_page(
    url: str,
    if_none_match: str | None = None,
    if_modified_since: str | None = None,
) -> FetchResult:
    """Fetch an HTML webpage with size caps, challenge detection, and 304 handling."""
    if not _is_ssrf_safe(url):
        logger.warning(f"SSRF blocked suspicious target URL: {url}")
        return FetchResult(
            url=url,
            status_code=0,
            html="",
            outcome="ssrf_blocked",
            simhash=0,
        )

    headers = {
        "User-Agent": f"{settings.crawler_user_agent} (contact: {settings.contact_email})",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    if if_none_match:
        headers["If-None-Match"] = if_none_match
    if if_modified_since:
        headers["If-Modified-Since"] = if_modified_since

    split_timeout = httpx.Timeout(connect=3.0, read=7.0, write=3.0, pool=2.0)

    try:
        async with httpx.AsyncClient(
            timeout=split_timeout,
            headers=headers,
            follow_redirects=True,
        ) as client:
            resp = await client.get(url)
            etag = resp.headers.get("etag")
            last_mod = resp.headers.get("last-modified")

            if resp.status_code == 304:
                return FetchResult(
                    url=url,
                    status_code=304,
                    html="",
                    outcome="304_not_modified",
                    simhash=0,
                    etag=etag,
                    last_modified=last_mod,
                )

            # Enforce 2MB cap
            text = resp.text[:MAX_HTML_BYTES]

            if is_bot_challenge(text, resp.status_code):
                logger.warning(f"Bot challenge detected at {url}")
                return FetchResult(
                    url=url,
                    status_code=resp.status_code,
                    html="",
                    outcome="blocked_by_site",
                    simhash=0,
                )

            if resp.status_code == 200:
                sh = compute_simhash(text)
                return FetchResult(
                    url=url,
                    status_code=200,
                    html=text,
                    outcome="ok",
                    simhash=sh,
                    etag=etag,
                    last_modified=last_mod,
                )

            return FetchResult(
                url=url,
                status_code=resp.status_code,
                html="",
                outcome=f"http_{resp.status_code}",
                simhash=0,
            )

    except httpx.ConnectTimeout:
        logger.warning(f"Connect timeout for {url}")
        return FetchResult(url=url, status_code=0, html="", outcome="connect_timeout", simhash=0)
    except httpx.ReadTimeout:
        logger.warning(f"Read timeout for {url}")
        return FetchResult(url=url, status_code=0, html="", outcome="read_timeout", simhash=0)
    except httpx.ConnectError:
        logger.warning(f"Connect error for {url}")
        return FetchResult(url=url, status_code=0, html="", outcome="connect_error", simhash=0)
    except Exception as e:
        err_name = type(e).__name__.lower()
        outcome = "tls_error" if "ssl" in err_name or "certificate" in str(e).lower() else "network_error"
        logger.warning(f"Fetch failed for {url} ({outcome}): {e}")
        return FetchResult(
            url=url,
            status_code=0,
            html="",
            outcome=outcome,
            simhash=0,
        )
