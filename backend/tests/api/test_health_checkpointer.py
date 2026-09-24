import pytest
from httpx import ASGITransport, AsyncClient
from langgraph.checkpoint.memory import MemorySaver

from app.main import app
from app.settings import settings


@pytest.mark.asyncio
async def test_health_reports_real_checkpointer() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/health")
        assert res.status_code == 200
        body = res.json()
        assert "checkpointer" in body
        assert "class" in body["checkpointer"]
        assert "is_durable" in body["checkpointer"]
        assert "max_loop_lag_ms_60s" in body


@pytest.mark.asyncio
async def test_health_detects_non_durable_checkpointer(monkeypatch: pytest.MonkeyPatch) -> None:
    # Set a MemorySaver on app.state
    app.state.checkpointer = MemorySaver()
    monkeypatch.setattr(settings, "testing", False, raising=False)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/health")
        assert res.status_code == 200
        body = res.json()
        assert body["checkpointer"]["class"] in ("MemorySaver", "InMemorySaver")
        assert body["checkpointer"]["is_durable"] is False
        assert body["status"] == "unhealthy"
