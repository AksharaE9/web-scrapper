"""
backend/tests/e2e/test_reconciliation.py — DB <-> API <-> UI Reconciliation Test Suite
"""
from __future__ import annotations

import pytest
from app.db.pool import get_conn


@pytest.mark.live
@pytest.mark.asyncio
async def test_db_api_ui_agree(run_id: str, api_client: any, page: any) -> None:
    """
    Asserts DB count == API count == UI rendered rows.
    If these three numbers ever disagree, the test names which layer lost the data.
    """
    async with get_conn() as conn:
        db = await (await conn.execute(
            """
            SELECT decision, count(*) n FROM run_results WHERE run_id=%s GROUP BY 1
            """,
            (run_id,),
        )).fetchall()
    db_counts = {r["decision"]: r["n"] for r in db}

    res = await api_client.get(f"/api/runs/{run_id}/leads?decision=accepted")
    api = res.json()
    api_total = api.get("total", 0)

    assert api_total == db_counts.get("accepted", 0), (
        f"API disagrees with DB: API returned {api_total}, DB has {db_counts.get('accepted', 0)}"
    )

    await page.goto(f"/runs/{run_id}?tab=accepted")
    rendered = await page.get_by_test_id("lead-row").count()
    assert rendered == api_total, (
        f"UI rendered {rendered}, API returned {api_total}"
    )
