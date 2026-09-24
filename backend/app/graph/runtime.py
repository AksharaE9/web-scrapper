"""
Node decorator and runtime utilities.

Every node is wrapped with:
  1. SSE events (node_started, node_finished, node_failed, node_progress)
  2. Wall-clock timeout enforcement via asyncio.timeout
  3. Tenacity retries on network and HTTP errors
  4. NodeError recording instead of run crash for non-critical nodes
  5. Monotonic sequence and iteration tracking
"""

from __future__ import annotations

import asyncio
import functools
import time
import traceback
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
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
_run_seq: dict[str, int] = {}


def set_event_bus(bus: Any) -> None:
    global _event_bus
    _event_bus = bus


def next_seq(run_id: str) -> int:
    """Return next monotonic sequence number for the given run_id."""
    global _run_seq
    seq = _run_seq.get(run_id, 0) + 1
    _run_seq[run_id] = seq
    return seq


async def _emit(run_id: str, event: str, data: dict[str, Any]) -> None:
    if _event_bus:
        await _event_bus.publish(run_id, event, data)


async def emit_node_progress(
    run_id: str,
    node: str,
    iteration: int = 0,
    done: int = 0,
    total: int = 0,
    current_domain: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Emit a structured node_progress event for long-running nodes."""
    payload: dict[str, Any] = {
        "node": node,
        "iteration": iteration,
        "seq": next_seq(run_id),
        "done": done,
        "total": total,
        "current_domain": current_domain,
    }
    if extra:
        payload.update(extra)
    await _emit(run_id, "node_progress", payload)


def node(
    name: str,
    critical: bool = True,
    max_retries: int = 0,
    budget_key: str | None = None,
    timeout_seconds: float = 300.0,
) -> Callable[[Callable[[RunState], Awaitable[dict[str, Any]]]], Callable[[RunState], Awaitable[dict[str, Any]]]]:
    """
    Decorator for LangGraph node functions.

    Enforces wall-clock timeouts, proper network retries, structured error handling,
    and SSE progress streaming with iteration and monotonic sequence numbers.
    """
    def decorator(fn: Callable[[RunState], Awaitable[dict[str, Any]]]) -> Callable[[RunState], Awaitable[dict[str, Any]]]:
        @functools.wraps(fn)
        async def wrapper(state: RunState) -> dict[str, Any]:
            run_id = state.get("run_id", "unknown")
            iteration = state.get("iteration", 0)
            t_start = time.monotonic()
            seq = next_seq(run_id)

            await _emit(run_id, "node_started", {
                "node": name,
                "iteration": iteration,
                "seq": seq,
                "attempt": 1,
            })
            log.info("Node started", node=name, run_id=run_id, iteration=iteration, seq=seq)

            # Check per-node budget if defined in state
            budget: Budget | None = state.get("budget")
            node_timeout = timeout_seconds
            if budget and budget.per_node and name in budget.per_node:
                node_timeout = float(budget.per_node[name].max_wall_seconds)

            attempt_fn = fn
            if max_retries > 0:
                attempt_fn = retry(
                    retry=retry_if_exception_type((
                        httpx.TransportError,
                        httpx.HTTPStatusError,
                        OSError,
                        TimeoutError,
                        asyncio.TimeoutError,
                        IOError,
                    )),
                    wait=wait_exponential_jitter(initial=1, max=30, jitter=2),
                    stop=stop_after_attempt(max_retries + 1),
                    reraise=True,
                )(fn)

            try:
                # Enforce wall-clock timeout
                async with asyncio.timeout(node_timeout):
                    result = await attempt_fn(state)

                elapsed = (time.monotonic() - t_start) * 1000
                await _emit(run_id, "node_finished", {
                    "node": name,
                    "iteration": iteration,
                    "seq": next_seq(run_id),
                    "elapsed_ms": round(elapsed, 1),
                })
                log.info("Node finished", node=name, run_id=run_id, elapsed_ms=elapsed, iteration=iteration)
                return result

            except Exception as exc:
                elapsed = (time.monotonic() - t_start) * 1000
                tb = traceback.format_exc()
                err_msg = str(exc) if str(exc) else f"{type(exc).__name__}: Node timed out or failed without message"
                err = NodeError(
                    node=name,
                    error=err_msg,
                    traceback=tb,
                    is_critical=critical,
                )
                await _emit(run_id, "node_failed", {
                    "node": name,
                    "iteration": iteration,
                    "seq": next_seq(run_id),
                    "error": err_msg,
                    "critical": critical,
                })
                log.error("Node failed", node=name, run_id=run_id, error=err_msg, iteration=iteration)

                if critical:
                    raise  # Propagate to worker → marks run as failed

                # Non-critical: record error and return empty partial update
                return {"errors": [err]}

        return wrapper
    return decorator
