"""
app/crawl/frontier.py — Per-domain polite frontier with AutoThrottle and bounded crawl budgets.
"""

from __future__ import annotations

import asyncio
import logging
import time
import urllib.parse
from collections import defaultdict, deque
from typing import Any

from app.crawl.fetcher import FetchResult, fetch_page
from app.crawl.robots import is_url_allowed

logger = logging.getLogger(__name__)


class DomainFrontier:
    """Polite per-domain crawler queue with AutoThrottle."""

    def __init__(
        self,
        max_pages_per_domain: int = 5,
        target_concurrency: float = 1.0,
        min_delay_secs: float = 0.5,
        max_delay_secs: float = 10.0,
    ) -> None:
        self.max_pages = max_pages_per_domain
        self.target_concurrency = target_concurrency
        self.min_delay = min_delay_secs
        self.max_delay = max_delay_secs

        self._domain_queues: dict[str, deque[str]] = defaultdict(deque)
        self._domain_fetched_count: dict[str, int] = defaultdict(int)
        self._domain_last_fetch_time: dict[str, float] = defaultdict(float)
        self._domain_current_delay: dict[str, float] = defaultdict(lambda: min_delay_secs)
        self._domain_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    def add_url(self, url: str) -> bool:
        domain = urllib.parse.urlparse(url).netloc
        if not domain:
            return False
        if self._domain_fetched_count[domain] + len(self._domain_queues[domain]) >= self.max_pages:
            return False
        self._domain_queues[domain].append(url)
        return True

    async def crawl_domain(self, domain: str, max_fetches: int = 3) -> list[FetchResult]:
        """Crawl queued URLs for a domain politely with AutoThrottle."""
        results: list[FetchResult] = []
        lock = self._domain_locks[domain]

        async with lock:
            while self._domain_queues[domain] and len(results) < max_fetches:
                if self._domain_fetched_count[domain] >= self.max_pages:
                    break

                url = self._domain_queues[domain].popleft()

                # 1. Robots.txt gate
                allowed = await is_url_allowed(url)
                if not allowed:
                    results.append(FetchResult(url=url, status_code=403, html="", outcome="robots_disallowed", simhash=0))
                    continue

                # 2. Politeness delay
                now = time.monotonic()
                last_time = self._domain_last_fetch_time[domain]
                delay = self._domain_current_delay[domain]
                elapsed = now - last_time
                if elapsed < delay:
                    await asyncio.sleep(delay - elapsed)

                # 3. Fetch
                t0 = time.monotonic()
                res = await fetch_page(url)
                duration = time.monotonic() - t0

                # 4. AutoThrottle adjustment:
                # new delay = mean(previous, target); non-200 can only increase delay
                target_delay = duration / self.target_concurrency
                if res.status_code == 200:
                    new_delay = (delay + target_delay) / 2.0
                else:
                    new_delay = max(delay, (delay + target_delay * 2) / 2.0)
                self._domain_current_delay[domain] = max(self.min_delay, min(self.max_delay, new_delay))

                self._domain_last_fetch_time[domain] = time.monotonic()
                self._domain_fetched_count[domain] += 1
                results.append(res)

        return results
