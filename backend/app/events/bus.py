"""
In-memory SSE Event Bus

Events flow: graph nodes → EventBus.publish() → SSE endpoint → browser.

This is NOT backed by Neon polling. The event bus lives entirely in process
memory. This keeps Neon compute idle between runs and ensures SSE latency < 100ms.

A heartbeat is sent every 15 seconds on each open SSE connection.
On server restart, historical events are not replayed (the frontend reconnects
and loads the current run state via GET /api/runs/{id} instead).
"""

from __future__ import annotations

import asyncio
import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import structlog

log = structlog.get_logger()

HEARTBEAT_INTERVAL = 15  # seconds


@dataclass
class SSEEvent:
    event: str
    data: dict[str, Any]
    run_id: str
    ts: float = field(default_factory=time.time)

    def encode(self) -> str:
        return f"event: {self.event}\ndata: {json.dumps(self.data)}\n\n"


class EventBus:
    """
    Simple fan-out event bus. Each run_id can have multiple SSE listeners
    (e.g., two browser tabs open on the same run detail page).
    """

    def __init__(self) -> None:
        # run_id → list of asyncio.Queue
        self._queues: dict[str, list[asyncio.Queue[SSEEvent | None]]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def subscribe(self, run_id: str | UUID) -> asyncio.Queue[SSEEvent | None]:
        """Register a new SSE listener for a run. Returns a queue to consume from."""
        run_id = str(run_id)
        q: asyncio.Queue[SSEEvent | None] = asyncio.Queue(maxsize=500)
        async with self._lock:
            self._queues[run_id].append(q)
        log.debug("SSE subscriber added", run_id=run_id, total=len(self._queues[run_id]))
        return q

    async def unsubscribe(self, run_id: str | UUID, q: asyncio.Queue[SSEEvent | None]) -> None:
        """Remove an SSE listener when the connection closes."""
        run_id = str(run_id)
        async with self._lock:
            try:
                self._queues[run_id].remove(q)
            except ValueError:
                pass
            if not self._queues[run_id]:
                del self._queues[run_id]
        log.debug("SSE subscriber removed", run_id=run_id)

    async def publish(self, run_id: str | UUID, event: str, data: dict[str, Any]) -> None:
        """Publish an event to all listeners of a run."""
        run_id = str(run_id)
        msg = SSEEvent(event=event, data=data, run_id=run_id)
        async with self._lock:
            queues = list(self._queues.get(run_id, []))
        dropped = 0
        for q in queues:
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                dropped += 1
        if dropped:
            log.warning("SSE queue full, events dropped", run_id=run_id, dropped=dropped)

    async def close_run(self, run_id: str | UUID) -> None:
        """Signal all listeners that this run is done (sends sentinel None)."""
        run_id = str(run_id)
        async with self._lock:
            queues = list(self._queues.get(run_id, []))
        for q in queues:
            try:
                q.put_nowait(None)
            except asyncio.QueueFull:
                pass


_default_bus: EventBus | None = None


def get_bus() -> EventBus:
    """Return the global singleton EventBus instance."""
    global _default_bus
    if _default_bus is None:
        _default_bus = EventBus()
    return _default_bus
