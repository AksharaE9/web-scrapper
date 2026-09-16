"""
Bounded Run Worker

Manages a pool of concurrent LangGraph run executions.
- Max concurrency: RUN_CONCURRENCY (default 2)
- On startup: resumes any runs in 'running' or 'queued' status
- Dequeues new runs in FIFO order from query_runs table
- Publishes all graph events to the EventBus for SSE delivery
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from psycopg import sql

from app.db.pool import get_conn
from app.events.bus import EventBus

log = structlog.get_logger()


class RunWorker:
    def __init__(self, event_bus: EventBus, concurrency: int = 2) -> None:
        self._bus = event_bus
        self._sem = asyncio.Semaphore(concurrency)
        self._task: asyncio.Task[None] | None = None
        self._running = False

    async def start(self) -> None:
        """Start the background worker loop and resume in-flight runs."""
        self._running = True
        await self._resume_inflight_runs()
        self._task = asyncio.create_task(self._poll_loop(), name="run_worker")
        log.info("RunWorker started")

    async def stop(self) -> None:
        """Gracefully stop the worker (allow in-flight runs to complete)."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        log.info("RunWorker stopped")

    async def enqueue(self, run_id: str | uuid.UUID) -> None:
        """Dispatches the run without waiting (fire-and-forget under the semaphore)."""
        asyncio.create_task(self._run_with_semaphore(str(run_id)))

    async def _resume_inflight_runs(self) -> None:
        try:
            async with get_conn() as conn:
                rows = await conn.execute(
                    "SELECT id FROM query_runs WHERE status IN ('running', 'queued') "
                    "ORDER BY created_at ASC"
                )
                run_ids = [str(row["id"]) async for row in rows]

            if run_ids:
                log.info("Resuming in-flight runs on startup", count=len(run_ids))
                for run_id in run_ids:
                    asyncio.create_task(self._run_with_semaphore(run_id))
        except Exception as e:
            log.warning("Could not resume in-flight runs on startup", error=str(e))

    async def _poll_loop(self) -> None:
        while self._running:
            await asyncio.sleep(2)

    async def _run_with_semaphore(self, run_id: str) -> None:
        async with self._sem:
            await self._execute_run(run_id)

    async def _execute_run(self, run_id: str) -> None:
        """Execute a LangGraph run and handle all state transitions."""
        log.info("Executing run", run_id=run_id)
        try:
            await self._set_status(run_id, "running", started_at=datetime.now(timezone.utc))

            # Import here to avoid circular imports at module load time
            from app.graph.build import get_compiled_graph
            from app.graph.state import QueryInput

            graph = get_compiled_graph()

            # Load the run input from DB
            async with get_conn() as conn:
                row = await (await conn.execute(
                    "SELECT raw_input FROM query_runs WHERE id = %s", (run_id,)
                )).fetchone()

            if not row:
                raise ValueError(f"Run {run_id} not found in query_runs")

            raw_input = row["raw_input"]
            if isinstance(raw_input, str):
                raw_input = json.loads(raw_input)

            # Build initial state from raw_input
            initial_state = {"run_id": run_id, "query": QueryInput(**raw_input)}
            config = {"configurable": {"thread_id": run_id}}

            # Execute the graph
            async for event in graph.astream(initial_state, config=config, stream_mode="updates"):
                for node_name, node_output in event.items():
                    await self._bus.publish(run_id, "node_progress", {
                        "node": node_name,
                        "output_keys": list(node_output.keys()) if isinstance(node_output, dict) else [],
                    })

            await self._set_status(run_id, "completed", finished_at=datetime.now(timezone.utc))
            await self._bus.publish(run_id, "run_finished", {"run_id": run_id, "status": "completed"})
            await self._bus.close_run(run_id)

        except asyncio.CancelledError:
            log.warning("Run cancelled", run_id=run_id)
            await self._set_status(run_id, "cancelled")
            raise
        except Exception as exc:
            log.exception("Run failed", run_id=run_id, error=str(exc))
            await self._set_status(run_id, "failed", error=str(exc))
            await self._bus.publish(run_id, "run_finished", {
                "run_id": run_id, "status": "failed", "error": str(exc)
            })
            await self._bus.close_run(run_id)

    async def _set_status(
        self,
        run_id: str,
        status: str,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
        error: str | None = None,
    ) -> None:
        updates: list[sql.Composable] = [sql.SQL("status = %s"), sql.SQL("updated_at = NOW()")]
        params: list[Any] = [status]
        if started_at:
            updates.append(sql.SQL("started_at = %s"))
            params.append(started_at.isoformat() if isinstance(started_at, datetime) else started_at)
        if finished_at:
            updates.append(sql.SQL("finished_at = %s"))
            params.append(finished_at.isoformat() if isinstance(finished_at, datetime) else finished_at)
        if error:
            updates.append(sql.SQL("error = %s"))
            params.append(error)
        params.append(run_id)
        update_query = sql.SQL("UPDATE query_runs SET {} WHERE id = %s").format(
            sql.SQL(", ").join(updates)
        )
        async with get_conn() as conn:
            await conn.execute(update_query, params)
            await conn.commit()
