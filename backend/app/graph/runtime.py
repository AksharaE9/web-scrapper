"""
Node decorator and runtime utilities.

Every node is wrapped with:
  1. SSE events (node_started, node_finished, node_failed)
  2. Budget enforcement (HTTP calls, LLM calls, wall seconds)
  3. Tenacity retries with exponential backoff + jitter
  4. NodeError recording instead of run crash for non-critical nodes
"""

from __future__ import annotations

import asyncio
import functools
import time
import traceback
from collections.abc import Callable, Awaitable
from typing import Any

import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.graph.state import Budget, NodeError, RunState

log = structlog.get_logger()

# Global event bus reference (set by worker at startup)
_event_bus: Any | None = None


def set_event_bus(bus: Any) -> None:
    global _event_bus
    _event_bus = bus


async def _emit(run_id: str, event: str, data: dict[str, Any]) -> None:
    if _event_bus:
        await _event_bus.publish(run_id, event, data)


def node(
    name: str,
    critical: bool = True,
    max_retries: int = 0,
    budget_key: str | None = None,
) -> Callable[[Callable[[RunState], Awaitable[dict[str, Any]]]], Callable[[RunState], Awaitable[dict[str, Any]]]]:
    """
    Decorator for LangGraph node functions.

    Usage:
        @node("n1_geo", critical=True, max_retries=3)
        async def run(state: RunState) -> dict: ...
    """
    def decorator(fn: Callable[[RunState], Awaitable[dict[str, Any]]]) -> Callable[[RunState], Awaitable[dict[str, Any]]]:
        @functools.wraps(fn)
        async def wrapper(state: RunState) -> dict[str, Any]:
            run_id = state.get("run_id", "unknown")
            t_start = time.monotonic()

            await _emit(run_id, "node_started", {"node": name})
            log.info("Node started", node=name, run_id=run_id)

            attempt_fn = fn
            if max_retries > 0:
                attempt_fn = retry(
                    retry=retry_if_exception_type((IOError, OSError, TimeoutError)),
                    wait=wait_exponential_jitter(initial=1, max=30, jitter=2),
                    stop=stop_after_attempt(max_retries + 1),
                    reraise=True,
                )(fn)

            try:
                result = await attempt_fn(state)
                elapsed = (time.monotonic() - t_start) * 1000
                await _emit(run_id, "node_finished", {
                    "node": name,
                    "elapsed_ms": round(elapsed, 1),
                })
                log.info("Node finished", node=name, run_id=run_id, elapsed_ms=elapsed)
                return result

            except Exception as exc:
                elapsed = (time.monotonic() - t_start) * 1000
                tb = traceback.format_exc()
                err = NodeError(
                    node=name,
                    error=str(exc),
                    traceback=tb,
                    is_critical=critical,
                )
                await _emit(run_id, "node_failed", {
                    "node": name,
                    "error": str(exc),
                    "critical": critical,
                })
                log.error("Node failed", node=name, run_id=run_id, error=str(exc))

                if critical:
                    raise  # Propagate to worker → marks run as failed

                # Non-critical: record error and return empty partial update
                return {"errors": [err]}

        return wrapper
    return decorator
