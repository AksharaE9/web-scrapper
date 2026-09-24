"""
Bounded Run Worker — Distributed Leased Work-Queue Engine

Features:
- PostgreSQL `FOR UPDATE SKIP LOCKED` atomic job claiming
- Leased execution with heartbeat renewal (prevents orphaned/stalled runs)
- Multi-worker safety (worker_id tracking and auto-reclamation of expired leases)
- Explicit fatal schema error detection (stops polling instead of infinite loop)
- Comprehensive worker health self-reporting (WorkerHealth)
- Stuck-run sweeper and poison-pill unclaimable protection
- Full exception capturing, task tracking, and SSE event dispatch
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Literal

if hasattr(sys.stdout, "reconfigure"):
    try:
        fn_out = getattr(sys.stdout, "reconfigure", None)
        if callable(fn_out):
            fn_out(encoding="utf-8", errors="replace")
        fn_err = getattr(sys.stderr, "reconfigure", None)
        if callable(fn_err):
            fn_err(encoding="utf-8", errors="replace")
    except Exception:
        pass

import psycopg.errors
import structlog
from psycopg import sql

from app.db.pool import get_conn
from app.events.bus import EventBus
from app.graph.build import get_compiled_graph
from app.graph.state import QueryInput
from app.settings import settings

log = structlog.get_logger()

FATAL_DB_ERRORS = (
    psycopg.errors.UndefinedColumn,
    psycopg.errors.UndefinedTable,
    psycopg.errors.InsufficientPrivilege,
    psycopg.errors.InvalidSchemaName,
)


@dataclass
class WorkerHealth:
    state: Literal["healthy", "degraded", "unhealthy", "fatal", "stopped"]
    worker_id: str
    active_runs: int
    free_slots: int
    last_successful_claim_at: str | None = None
    last_poll_at: str | None = None
    last_error: str | None = None
    error_code: str | None = None
    consecutive_errors: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RunWorker:
    def __init__(
        self,
        event_bus: EventBus,
        concurrency: int = 2,
        poll_interval_s: float = 1.0,
        lease_duration_minutes: int = 15,
        max_queue_wait_minutes: int = 30,
    ) -> None:
        self._bus = event_bus
        self._concurrency = max(1, concurrency)
        self._poll_interval_s = max(0.2, poll_interval_s)
        self._lease_duration_minutes = lease_duration_minutes
        self._max_queue_wait_minutes = max_queue_wait_minutes
        self.worker_id = f"worker-{uuid.uuid4().hex[:8]}"

        self._active_tasks: set[asyncio.Task[None]] = set()
        self._poll_task: asyncio.Task[None] | None = None
        self._sweeper_task: asyncio.Task[None] | None = None
        self._running = False

        self._consecutive_errors = 0
        self._last_error: str | None = None
        self._error_code: str | None = None
        self._last_successful_claim_at: datetime | None = None
        self._last_poll_at: datetime | None = None
        self._fatal_error: str | None = None

    @property
    def is_fatal(self) -> bool:
        return self._fatal_error is not None

    @property
    def health_state(self) -> str:
        if self._fatal_error:
            return "fatal"
        if not self._running:
            return "stopped"
        if self._consecutive_errors >= 5:
            return "unhealthy"
        if self._consecutive_errors > 0:
            return "degraded"
        return "healthy"

    @property
    def health(self) -> WorkerHealth:
        return WorkerHealth(
            state=self.health_state,  # type: ignore
            worker_id=self.worker_id,
            active_runs=len(self._active_tasks),
            free_slots=self._free_slots(),
            last_successful_claim_at=self._last_successful_claim_at.isoformat() if self._last_successful_claim_at else None,
            last_poll_at=self._last_poll_at.isoformat() if self._last_poll_at else None,
            last_error=self._last_error or self._fatal_error,
            error_code=self._error_code or ("schema_error" if self._fatal_error else None),
            consecutive_errors=self._consecutive_errors,
        )

    @property
    def active_runs_count(self) -> int:
        return len(self._active_tasks)

    def _free_slots(self) -> int:
        return max(0, self._concurrency - len(self._active_tasks))

    async def start(self) -> None:
        """Start the leased polling worker and reclaim expired leases."""
        self._running = True
        await self._reclaim_expired_leases()
        self._poll_task = asyncio.create_task(self._poll_loop(), name=f"run_worker_{self.worker_id}")
        self._sweeper_task = asyncio.create_task(self._sweeper_loop(), name=f"sweeper_{self.worker_id}")
        log.info("RunWorker started with leased queue", worker_id=self.worker_id, concurrency=self._concurrency)

    async def stop(self) -> None:
        """Gracefully stop the worker, release active leases, and cancel tasks."""
        self._running = False
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass

        if self._sweeper_task:
            self._sweeper_task.cancel()
            try:
                await self._sweeper_task
            except asyncio.CancelledError:
                pass

        # Release leases on active running runs so another worker can claim them immediately
        try:
            async with get_conn() as conn:
                await conn.execute(
                    """
                    UPDATE query_runs
                       SET worker_id = NULL,
                           lease_until = NULL,
                           updated_at = NOW()
                     WHERE worker_id = %s AND status = 'running'
                    """,
                    (self.worker_id,),
                )
                await conn.commit()
                log.info("Released active leases on worker shutdown", worker_id=self.worker_id)
        except Exception as e:
            log.warning("Failed to release leases during shutdown", error=str(e))

        if self._active_tasks:
            log.info("Waiting for active run tasks to finish", count=len(self._active_tasks))
            await asyncio.gather(*list(self._active_tasks), return_exceptions=True)

    async def enqueue(self, run_id: str | uuid.UUID) -> None:
        """Signals immediate poll or spawns a direct execution if slots are available."""
        if self.is_fatal:
            raise RuntimeError(f"Worker is in fatal error state ({self._fatal_error}) and cannot accept jobs")
        run_str = str(run_id)
        if self._free_slots() > 0:
            asyncio.create_task(self._claim_and_dispatch_specific(run_str))

    async def cancel_run(self, run_id: str | uuid.UUID) -> None:
        """Cancel an active run in worker and update its database status."""
        run_str = str(run_id)
        # Cancel any active running task associated with this run
        for t in list(self._active_tasks):
            if getattr(t, "get_name", lambda: "")() == f"run_{run_str}":
                t.cancel()
        await self._set_status(
            run_str,
            "cancelled",
            completion_reason="cancelled_by_user",
            finished_at=datetime.now(timezone.utc),
        )

    async def _claim_and_dispatch_specific(self, run_id: str) -> None:
        try:
            async with get_conn() as conn:
                res = await conn.execute(
                    """
                    UPDATE query_runs
                       SET status = 'running',
                           started_at = COALESCE(started_at, NOW()),
                           worker_id = %s,
                           lease_until = NOW() + (%s || ' minutes')::interval,
                           updated_at = NOW()
                     WHERE id = %s
                       AND (status = 'queued' OR (status = 'running' AND (lease_until IS NULL OR lease_until < NOW())))
                 RETURNING id
                    """,
                    (self.worker_id, self._lease_duration_minutes, run_id),
                )
                row = await res.fetchone()
                if row:
                    await conn.commit()
                    self._last_successful_claim_at = datetime.now(timezone.utc)
                    self._dispatch_run(str(row["id"]))
        except FATAL_DB_ERRORS as e:
            self._fatal_error = str(e)
            self._error_code = "schema_error"
            self._running = False
            log.critical("Worker cannot claim specific run — fatal database schema error", error=str(e), run_id=run_id)
            raise
        except Exception as e:
            log.error("Could not claim specific run", run_id=run_id, error=str(e))

    async def _reclaim_expired_leases(self) -> None:
        """Reclaim any runs whose lease expired while previous worker was offline."""
        try:
            async with get_conn() as conn:
                res = await conn.execute("""
                    UPDATE query_runs
                       SET status = 'queued',
                           worker_id = NULL,
                           lease_until = NULL,
                           updated_at = NOW()
                     WHERE status = 'running'
                       AND lease_until IS NOT NULL
                       AND lease_until < NOW()
                 RETURNING id
                """)
                reclaimed = await res.fetchall()
                if reclaimed:
                    await conn.commit()
                    log.info("Reclaimed expired run leases on startup", count=len(reclaimed))
        except FATAL_DB_ERRORS as e:
            self._fatal_error = str(e)
            self._error_code = "schema_error"
            self._running = False
            log.critical("Fatal schema error during startup lease reclamation", error=str(e))
            raise
        except Exception as e:
            log.error("Could not reclaim expired leases on startup", error=str(e))
            raise

    async def _poll_loop(self) -> None:
        """Active polling loop claiming queued or expired runs via Postgres FOR UPDATE SKIP LOCKED."""
        while self._running:
            self._last_poll_at = datetime.now(timezone.utc)
            try:
                free = self._free_slots()
                if free > 0:
                    async with get_conn() as conn:
                        res = await conn.execute(
                            """
                            UPDATE query_runs
                               SET status = 'running',
                                   started_at = COALESCE(started_at, NOW()),
                                   worker_id = %s,
                                   lease_until = NOW() + (%s || ' minutes')::interval,
                                   updated_at = NOW()
                             WHERE id IN (
                                 SELECT id FROM query_runs
                                  WHERE status = 'queued'
                                     OR (status = 'running' AND lease_until IS NOT NULL AND lease_until < NOW())
                                  ORDER BY created_at ASC
                                  FOR UPDATE SKIP LOCKED
                                  LIMIT %s
                             )
                         RETURNING id
                            """,
                            (self.worker_id, self._lease_duration_minutes, free),
                        )
                        claimed = await res.fetchall()
                        if claimed:
                            await conn.commit()
                            self._consecutive_errors = 0
                            self._last_successful_claim_at = datetime.now(timezone.utc)
                            for r in claimed:
                                self._dispatch_run(str(r["id"]))

            except asyncio.CancelledError:
                break
            except FATAL_DB_ERRORS as e:
                self._fatal_error = str(e)
                self._error_code = "schema_error"
                self._running = False
                log.critical("Worker cannot operate — fatal database schema error in poll loop", error=str(e))
                raise
            except Exception as e:
                self._consecutive_errors += 1
                self._last_error = str(e)
                self._error_code = "poll_error"
                log.exception("Worker poll loop exception", error=str(e), consecutive_errors=self._consecutive_errors)
                backoff = min(self._poll_interval_s * (2 ** self._consecutive_errors), 30.0)
                await asyncio.sleep(backoff)
                continue

            await asyncio.sleep(self._poll_interval_s)

    async def _sweep_stuck_runs(self) -> int:
        """Sweeps and fails runs queued longer than max_queue_wait_minutes."""
        async with get_conn() as conn:
            res = await conn.execute(
                """
                UPDATE query_runs
                   SET status = 'failed',
                       error = %s,
                       error_code = 'queue_timeout',
                       finished_at = NOW(),
                       updated_at = NOW()
                 WHERE status = 'queued'
                   AND created_at < NOW() - (%s || ' minutes')::interval
             RETURNING id
                """,
                (
                    f"Run remained in queue for more than {self._max_queue_wait_minutes} minutes without being claimed by a worker.",
                    self._max_queue_wait_minutes,
                ),
            )
            stuck_runs = await res.fetchall()
            if stuck_runs:
                await conn.commit()
                log.warning(
                    "Stuck-run sweeper terminated expired queued runs",
                    count=len(stuck_runs),
                    run_ids=[str(r["id"]) for r in stuck_runs],
                )
            return len(stuck_runs)

    async def _sweeper_loop(self) -> None:
        """Stuck-run sweeper background loop: runs every 60s."""
        while self._running:
            try:
                await asyncio.sleep(60.0)
                if not self._running:
                    break
                await self._sweep_stuck_runs()
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("Stuck-run sweeper encountered error", error=str(e))

    def _dispatch_run(self, run_id: str) -> None:
        task = asyncio.create_task(self._execute_run(run_id), name=f"run_{run_id}")
        self._active_tasks.add(task)

        def _on_done(t: asyncio.Task[None]) -> None:
            self._active_tasks.discard(t)
            if not t.cancelled():
                exc = t.exception()
                if exc:
                    log.error("Run task failed with unhandled exception", run_id=run_id, exc_info=exc)

        task.add_done_callback(_on_done)

    async def _execute_run(self, run_id: str) -> None:
        """Execute a LangGraph run with heartbeat lease renewal and error handling."""
        log.info("Executing run pipeline", run_id=run_id, worker_id=self.worker_id)
        heartbeat_task: asyncio.Task[None] | None = None

        try:
            # Heartbeat lease renewer
            async def _heartbeat() -> None:
                while True:
                    await asyncio.sleep(60.0)
                    try:
                        async with get_conn() as conn:
                            await conn.execute(
                                """
                                UPDATE query_runs
                                   SET lease_until = NOW() + (%s || ' minutes')::interval,
                                       updated_at = NOW()
                                 WHERE id = %s AND worker_id = %s
                                """,
                                (self._lease_duration_minutes, run_id, self.worker_id),
                            )
                            await conn.commit()
                    except Exception as err:
                        log.warning("Failed to renew run lease heartbeat", run_id=run_id, error=str(err))

            heartbeat_task = asyncio.create_task(_heartbeat(), name=f"heartbeat_{run_id}")

            # Load and validate raw_input
            async with get_conn() as conn:
                row = await (await conn.execute(
                    "SELECT raw_input FROM query_runs WHERE id = %s", (run_id,)
                )).fetchone()

            raw_input = row["raw_input"] if row else None
            if isinstance(raw_input, str):
                try:
                    raw_input = json.loads(raw_input)
                except Exception as json_err:
                    log.error("Failed to parse raw_input JSON string", run_id=run_id, error=str(json_err))
                    raw_input = None

            if not isinstance(raw_input, dict) or not raw_input:
                error_msg = f"corrupt_run_row: Run {run_id} has invalid or missing raw_input: {raw_input}"
                log.error("Corrupt run input, aborting execution", run_id=run_id)
                await self._set_status(
                    run_id,
                    "failed",
                    error=error_msg,
                    error_code="corrupt_run_row",
                    retryable=False,
                    completion_reason="corrupt_run_row",
                    finished_at=datetime.now(timezone.utc),
                )
                return

            try:
                query_input = QueryInput(**raw_input)
            except Exception as e:
                error_msg = f"corrupt_run_row: Stored query data is invalid: {e}"
                log.error("Invalid query input schema, aborting execution", run_id=run_id, error=str(e))
                await self._set_status(
                    run_id,
                    "failed",
                    error=error_msg,
                    error_code="corrupt_run_row",
                    retryable=False,
                    completion_reason="corrupt_run_row",
                    finished_at=datetime.now(timezone.utc),
                )
                return

            graph = get_compiled_graph()
            initial_state: dict[str, Any] = {
                "run_id": run_id,
                "query": query_input,
                "input": query_input,
                "errors": [],
                "source_stats": {},
            }
            config = {"configurable": {"thread_id": run_id}}

            # Stream LangGraph execution
            async for _ in graph.astream(initial_state, config=config):
                pass

        except asyncio.CancelledError:
            log.warning("Run was cancelled during execution", run_id=run_id)
            has_accepted_leads = False
            try:
                async with get_conn() as conn:
                    res = await conn.execute(
                        "SELECT count(*) as c FROM run_results WHERE run_id = %s AND decision = 'accepted'",
                        (run_id,),
                    )
                    r_row = await res.fetchone()
                    if r_row and (r_row["c"] or 0) > 0:
                        has_accepted_leads = True
            except Exception as e:
                log.warning("Failed to check accepted count on cancellation", run_id=run_id, error=str(e))
                has_accepted_leads = False

            await self._set_status(
                run_id,
                "cancelled",
                completion_reason="cancelled_by_user",
                finished_at=datetime.now(timezone.utc),
            )
            await self._bus.publish(run_id, "run_cancelled", {
                "run_id": run_id,
                "status": "cancelled",
                "has_partial": has_accepted_leads,
            })
        except Exception as exc:
            log.exception("Pipeline run execution failed", run_id=run_id, error=str(exc))
            err_code = getattr(exc, "error_code", "internal")

            # Check if partial leads were persisted
            has_accepted_leads = False
            try:
                async with get_conn() as conn:
                    res = await conn.execute(
                        "SELECT count(*) as c FROM run_results WHERE run_id = %s AND decision = 'accepted'",
                        (run_id,),
                    )
                    r_row = await res.fetchone()
                    if r_row and (r_row["c"] or 0) > 0:
                        has_accepted_leads = True
            except Exception as e:
                log.warning("Failed to check accepted leads count during failure handling", exc=str(e), run_id=run_id)
                has_accepted_leads = False

            # Partial beats failed: if accepted leads exist, mark partial
            final_status = "partial" if has_accepted_leads else "failed"
            is_deterministic = err_code in ("corrupt_run_row", "not_retryable", "schema_error", "internal")
            retryable_flag = False if is_deterministic else True

            await self._set_status(
                run_id,
                final_status,
                error=str(exc),
                error_code=err_code,
                retryable=retryable_flag,
                completion_reason="partial_failure" if has_accepted_leads else "failed",
                finished_at=datetime.now(timezone.utc),
            )
            await self._bus.publish(run_id, "run_failed" if final_status == "failed" else "run_completed", {
                "run_id": run_id,
                "error": str(exc),
                "error_code": err_code,
                "status": final_status,
                "retryable": retryable_flag,
            })
        finally:
            if heartbeat_task:
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass

    async def _set_status(
        self,
        run_id: str,
        status: str,
        error: str | None = None,
        error_code: str | None = None,
        retryable: bool | None = None,
        completion_reason: str | None = None,
        attempt_strategy: str | None = None,
        finished_at: datetime | None = None,
    ) -> None:
        async with get_conn() as conn:
            await conn.execute(
                """
                UPDATE query_runs
                   SET status = %s,
                       error = %s,
                       error_code = %s,
                       retryable = COALESCE(%s, retryable),
                       completion_reason = COALESCE(%s, completion_reason),
                       attempt_strategy = COALESCE(%s, attempt_strategy),
                       finished_at = %s,
                       worker_id = NULL,
                       lease_until = NULL,
                       updated_at = NOW()
                 WHERE id = %s
                """,
                (status, error, error_code, retryable, completion_reason, attempt_strategy, finished_at, run_id),
            )
            await conn.commit()
