"""
tests/api/test_compliance_export.py — Test pre-export compliance endpoint and CSV/XLSX export disclosures.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app


@pytest.mark.asyncio
async def test_export_compliance_endpoint() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Fetch runs list
        runs_resp = await client.get("/api/runs")
        assert runs_resp.status_code == 200
        runs = runs_resp.json()
        assert len(runs) > 0
        run_id = runs[0]["id"]

        # 2. Test compliance preview endpoint
        comp_resp = await client.get(f"/api/runs/{run_id}/export/compliance")
        assert comp_resp.status_code == 200
        comp_data = comp_resp.json()
        assert "total_leads" in comp_data
        assert "mobile_subscribers_count" in comp_data
        assert "dnd_notice" in comp_data
        assert "TRAI" in comp_data["dnd_notice"]
        assert "lawful_basis" in comp_data
        assert "DPDP" in comp_data["lawful_basis"]

        # 3. Test CSV export includes compliance headers
        csv_resp = await client.get(f"/api/runs/{run_id}/export?format=csv")
        assert csv_resp.status_code == 200
        lines = csv_resp.text.splitlines()
        header = lines[0]
        assert "dnd_subscriber_risk" in header
        assert "compliance_basis" in header

        # 4. Test XLSX export returns valid application/vnd.openxmlformats binary
        xlsx_resp = await client.get(f"/api/runs/{run_id}/export?format=xlsx")
        assert xlsx_resp.status_code == 200
        assert xlsx_resp.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        assert len(xlsx_resp.content) > 1000
