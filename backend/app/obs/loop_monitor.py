"""
app/obs/loop_monitor.py — Event loop lag monitoring.
Surfaces event loop stalls and reports max_loop_lag_ms_60s.
"""

from __future__ import annotations

import asyncio
import collections
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

# Ring buffer of (timestamp, lag_ms) for the last 60 seconds
_LAG_SAMPLES: collections.deque[tuple[float, float]] = collections.deque(maxlen=1200)
_MONITOR_TASK: asyncio.Task[None] | None = None


async def loop_lag_monitor(threshold_ms: float = 250.0) -> None:
    """
    Background coroutine measuring event loop lag.
    Logs warning if lag exceeds threshold_ms.
    """
    sample_interval = 0.1
    while True:
        t0 = time.monotonic()
        try:
            await asyncio.sleep(sample_interval)
        except asyncio.CancelledError:
            break
        except Exception:
            break

        now = time.monotonic()
        lag_ms = max(0.0, (now - t0 - sample_interval) * 1000.0)
        _LAG_SAMPLES.append((now, lag_ms))

        if lag_ms > threshold_ms:
            logger.warning(f"Event loop blocked for {lag_ms:.1f}ms (threshold: {threshold_ms}ms)")


def get_max_loop_lag_ms_60s() -> float:
    """Return the maximum loop lag (in milliseconds) recorded in the last 60 seconds."""
    now = time.monotonic()
    cutoff = now - 60.0
    # Prune old samples
    while _LAG_SAMPLES and _LAG_SAMPLES[0][0] < cutoff:
        _LAG_SAMPLES.popleft()

    if not _LAG_SAMPLES:
        return 0.0
    return round(max(lag for _, lag in _LAG_SAMPLES), 1)


def start_loop_monitor() -> asyncio.Task[None]:
    global _MONITOR_TASK
    if _MONITOR_TASK is None or _MONITOR_TASK.done():
        _MONITOR_TASK = asyncio.create_task(loop_lag_monitor())
    return _MONITOR_TASK


def stop_loop_monitor() -> None:
    global _MONITOR_TASK
    if _MONITOR_TASK and not _MONITOR_TASK.done():
        _MONITOR_TASK.cancel()
        _MONITOR_TASK = None
