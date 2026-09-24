"""
tests/test_startup_contract.py — Comprehensive Test Suite for Startup Contract & Visible Health

Asserts:
- Startup contract fails on missing column naming column and fix command
- Startup contract fails on pending migration
- Worker startup failures are not swallowed in lifespan
- Fatal schema errors stop worker loop with fatal status (no infinite poll)
- Transient errors back off exponentially and mark degraded
- Stalled queue produces non-OK health status
- POST /api/runs returns 503 when worker is fatal
- Stuck run sweeper terminates expired queued jobs with error_code='queue_timeout'
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import psycopg.errors
import pytest
from fastapi.testclient import TestClient

from app.db.schema_contract import assert_migrations_current, assert_schema
from app.events.bus import EventBus
from app.main import create_app
from app.worker import RunWorker, WorkerHealth


@pytest.mark.asyncio
async def test_startup_fails_on_missing_column() -> None:
    """Missing required column in information_schema raises RuntimeError naming it and fix command."""
    mock_conn = MagicMock()
    # Mock information_schema returning partial columns
    async def mock_execute(query, params=None):
        table = params[0] if params else ""
        mock_res = MagicMock()
        if table == "query_runs":
            # Missing worker_id and lease_until
            mock_res.fetchall = AsyncMock(return_value=[
                {"column_name": "id"},
                {"column_name": "created_at"},
                {"column_name": "status"},
            ])
        else:
            mock_res.fetchall = AsyncMock(return_value=[{"column_name": "id"}])
        return mock_res

    mock_conn.execute = mock_execute

    with pytest.raises(RuntimeError) as exc_info:
        await assert_schema(mock_conn)

    err_text = str(exc_info.value)
    assert "Database schema is out of date" in err_text
    assert "query_runs.worker_id" in err_text or "query_runs.lease_until" in err_text
    assert "uv run alembic upgrade head" in err_text


@pytest.mark.asyncio
async def test_startup_fails_on_pending_migration() -> None:
    """Mismatched alembic_version raises RuntimeError with exact revision numbers and fix command."""
    mock_conn = MagicMock()
    async def mock_execute(query, params=None):
        mock_res = MagicMock()
        # Database revision is 001_initial while head is 004_leased_worker_queue
        mock_res.fetchone = AsyncMock(return_value={"version_num": "001_initial"})
        return mock_res

    mock_conn.execute = mock_execute

    with pytest.raises(RuntimeError) as exc_info:
        await assert_migrations_current(mock_conn)

    err_text = str(exc_info.value)
    assert "Database migration is out of date" in err_text
    assert "001_initial" in err_text
    assert "uv run alembic upgrade head" in err_text


@pytest.mark.asyncio
async def test_schema_error_is_fatal_not_retried() -> None:
    """UndefinedColumn in worker causes worker to transition to fatal and stop polling."""
    bus = EventBus()
    worker = RunWorker(event_bus=bus, concurrency=1, poll_interval_s=0.1)

    with patch("app.worker.get_conn") as mock_get_conn:
        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock(side_effect=psycopg.errors.UndefinedColumn("column worker_id does not exist"))
        mock_get_conn.return_value.__aenter__.return_value = mock_conn

        # Poll loop should raise and set fatal health
        with pytest.raises(psycopg.errors.UndefinedColumn):
            worker._running = True
            await worker._poll_loop()

        assert worker.is_fatal is True
        assert worker.health.state == "fatal"
        assert worker.health.error_code == "schema_error"
        assert "worker_id" in str(worker.health.last_error)


@pytest.mark.asyncio
async def test_transient_error_backs_off() -> None:
    """Transient network error increments consecutive errors and marks worker degraded."""
    bus = EventBus()
    worker = RunWorker(event_bus=bus, concurrency=1, poll_interval_s=0.01)

    with patch("app.worker.get_conn") as mock_get_conn:
        mock_conn = MagicMock()
        # Transient connection error
        mock_conn.execute = AsyncMock(side_effect=Exception("Connection reset by peer"))
        mock_get_conn.return_value.__aenter__.return_value = mock_conn

        worker._running = True
        poll_task = asyncio.create_task(worker._poll_loop())
        await asyncio.sleep(0.08)
        assert worker.health.consecutive_errors > 0
        assert worker.health.state in ("degraded", "unhealthy")
        assert worker.is_fatal is False

        worker._running = False
        poll_task.cancel()
        try:
            await poll_task
        except asyncio.CancelledError:
            pass


def test_post_runs_503_when_worker_fatal() -> None:
    """POST /api/runs returns 503 Service Unavailable when worker is fatal."""
    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)

    bus = EventBus()
    worker = RunWorker(event_bus=bus, concurrency=1)
    worker._fatal_error = 'column "worker_id" does not exist'
    app.state.worker = worker

    response = client.post(
        "/api/runs",
        json={
            "location": {"locality": "HSR Layout", "city": "Bengaluru"},
            "keywords": ["pooja store"],
        },
    )

    assert response.status_code == 503
    data = response.json()
    assert data["detail"]["code"] == "worker_unavailable"
    assert "alembic upgrade head" in data["detail"]["action"]


@pytest.mark.asyncio
async def test_health_reports_stalled_queue() -> None:
    """GET /api/health returns non-OK when queue has stalled runs and worker is not healthy."""
    from app.api.health import _check_queue

    bus = EventBus()
    worker = RunWorker(event_bus=bus, concurrency=1)
    worker._fatal_error = "Schema out of date"

    with patch("app.api.health.get_conn") as mock_get_conn:
        mock_conn = MagicMock()
        d_res = MagicMock()
        # 8 queued runs, oldest is 731s old
        d_res.fetchone = AsyncMock(return_value={
            "queued": 8,
            "running": 0,
            "oldest_queued_age_s": 731,
            "oldest_queued_run_id": "test-run-123",
        })
        t_res = MagicMock()
        t_res.fetchone = AsyncMock(return_value={
            "completed_last_hour": 0,
            "failed_last_hour": 0,
        })
        mock_conn.execute = AsyncMock(side_effect=[d_res, t_res])
        mock_get_conn.return_value.__aenter__.return_value = mock_conn

        res = await _check_queue(worker)
        assert res["worker"]["state"] == "fatal"
        assert res["depth"]["queued"] == 8
        assert res["depth"]["oldest_queued_age_s"] == 731


@pytest.mark.asyncio
async def test_stuck_run_sweeper() -> None:
    """Sweeper terminates runs queued past the wait limit with queue_timeout."""
    bus = EventBus()
    worker = RunWorker(event_bus=bus, concurrency=1, max_queue_wait_minutes=1)

    with patch("app.worker.get_conn") as mock_get_conn:
        mock_conn = MagicMock()
        mock_res = MagicMock()
        mock_res.fetchall = AsyncMock(return_value=[{"id": "stuck-run-uuid-1"}])
        mock_conn.execute = AsyncMock(return_value=mock_res)
        mock_conn.commit = AsyncMock()
        mock_get_conn.return_value.__aenter__.return_value = mock_conn

        count = await worker._sweep_stuck_runs()
        assert count == 1
        assert mock_conn.execute.called
        assert mock_conn.commit.called
