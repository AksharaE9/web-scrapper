"""
tests/api/test_sse_stream.py — SSE event stream causal ordering and schema validation.
"""

from __future__ import annotations

import json
import pytest
from app.graph.runtime import _emit, set_event_bus


class MockEventBus:
    def __init__(self) -> None:
        self.events: list[tuple[str, str, dict]] = []

    async def publish(self, run_id: str, event: str, data: dict) -> None:
        self.events.append((run_id, event, data))


@pytest.mark.asyncio
async def test_sse_event_causal_ordering() -> None:
    bus = MockEventBus()
    set_event_bus(bus)

    run_id = "test_run_123"
    await _emit(run_id, "node_started", {"node": "n1_geo"})
    await _emit(run_id, "node_finished", {"node": "n1_geo", "elapsed_ms": 120})

    assert len(bus.events) == 2
    r1, e1, d1 = bus.events[0]
    r2, e2, d2 = bus.events[1]

    assert r1 == run_id and e1 == "node_started" and d1["node"] == "n1_geo"
    assert r2 == run_id and e2 == "node_finished" and d2["node"] == "n1_geo"
    assert "elapsed_ms" in d2
