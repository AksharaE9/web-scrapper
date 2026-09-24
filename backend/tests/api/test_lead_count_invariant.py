"""
tests/api/test_lead_count_invariant.py — Lead count synchronization invariants (§3).

Guarantees:
1. For any run and any filter set: tab count == total == rows rendered == export row count.
2. Decisions (accepted, review, rejected) are disjoint and sum to all total.
3. Suppression matches via EXISTS never duplicate rows.
4. decision is NOT NULL in run_results (migration 006).
5. Default export matches the Accepted tab.
"""

from __future__ import annotations

import uuid
from typing import Any
import pytest
from httpx import ASGITransport, AsyncClient
from psycopg import sql

from app.db.pool import get_conn
from app.main import app


@pytest.fixture
async def seeded_run() -> str:
    """Fixture to seed a test run with businesses across accepted, review, and rejected states."""
    run_id = str(uuid.uuid4())

    async with get_conn() as conn:
        # Create query run
        await conn.execute(
            """
            INSERT INTO query_runs (id, created_at, status, raw_input, keywords, locality, city, country, stats)
            VALUES (%s, NOW(), 'completed', '{"query": "gyms in Whitefield"}'::jsonb, ARRAY['gym'], 'Whitefield', 'Bengaluru', 'India', '{"geo": {"centroid": [77.75, 12.97]}}'::jsonb)
            """,
            (run_id,),
        )

        # Create 3 businesses for accepted
        for i in range(3):
            b_id = str(uuid.uuid4())
            await conn.execute(
                """
                INSERT INTO businesses (id, canonical_name, name_norm, primary_category, phones_e164, website_domain, geom)
                VALUES (%s, %s, %s, 'Gym', ARRAY['+91987654321' || %s], %s, ST_SetSRID(ST_MakePoint(77.75, 12.97), 4326))
                """,
                (b_id, f"Accepted Gym {i}", f"accepted gym {i}", str(i), f"acceptedgym{i}.com"),
            )
            await conn.execute(
                """
                INSERT INTO run_results (run_id, business_id, keyword, rank, match_score, is_new_business, decision, relevance_p)
                VALUES (%s, %s, 'gym', %s, 0.95, true, 'accepted', 0.95)
                """,
                (run_id, b_id, i + 1),
            )

        # Create 2 businesses for review
        for i in range(2):
            b_id = str(uuid.uuid4())
            await conn.execute(
                """
                INSERT INTO businesses (id, canonical_name, name_norm, primary_category, phones_e164, website_domain, geom)
                VALUES (%s, %s, %s, 'Fitness Studio', ARRAY['+91887654321' || %s], %s, ST_SetSRID(ST_MakePoint(77.75, 12.97), 4326))
                """,
                (b_id, f"Review Studio {i}", f"review studio {i}", str(i), f"reviewstudio{i}.com"),
            )
            await conn.execute(
                """
                INSERT INTO run_results (run_id, business_id, keyword, rank, match_score, is_new_business, decision, relevance_p)
                VALUES (%s, %s, 'gym', %s, 0.65, true, 'review', 0.65)
                """,
                (run_id, b_id, i + 4),
            )

        # Create 2 rejected candidates in rejected_candidates table
        for i in range(2):
            await conn.execute(
                """
                INSERT INTO rejected_candidates (run_id, source, source_record_id, name, reason, reason_code, relevance_p, features)
                VALUES (%s, 'overture', %s, %s, 'low_relevance', 'low_relevance_score', 0.20, '{}'::jsonb)
                """,
                (run_id, f"ov_rej_{i}", f"Rejected Shop {i}"),
            )

        await conn.commit()

    return run_id


@pytest.mark.asyncio
@pytest.mark.parametrize("decision", ["accepted", "review", "rejected"])
async def test_count_equals_rows_equals_export(seeded_run: str, decision: str) -> None:
    """Invariant: tab count == total == rows rendered == export row count."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as api:
        resp = (await api.get(f"/api/runs/{seeded_run}/leads?decision={decision}&limit=1000")).json()
        assert resp["total"] == len(resp["items"]), f"total {resp['total']} disagrees with items {len(resp['items'])}"
        assert resp["counts"][decision] == resp["total"], f"tab count {resp['counts'][decision]} disagrees with total {resp['total']}"

        csv_resp = await api.get(f"/api/runs/{seeded_run}/export?decision={decision}")
        assert csv_resp.status_code == 200
        csv_rows = len(csv_resp.text.strip().splitlines()) - 1  # minus header
        assert csv_rows == resp["total"], f"export {csv_rows} != API {resp['total']}"


@pytest.mark.asyncio
async def test_decisions_are_disjoint_and_sum_to_total(seeded_run: str) -> None:
    """Invariant: counts.accepted + counts.review + counts.rejected == decision=all total."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as api:
        c = (await api.get(f"/api/runs/{seeded_run}/leads?limit=1")).json()["counts"]
        all_ = (await api.get(f"/api/runs/{seeded_run}/leads?decision=all&limit=5000")).json()
        assert c["accepted"] + c["review"] + c["rejected"] == all_["total"]


@pytest.mark.asyncio
async def test_suppression_join_does_not_multiply(seeded_run: str) -> None:
    """Invariant: EXISTS check must never duplicate business rows even if multiple suppression rules match."""
    async with get_conn() as conn:
        # Seed 3 separate suppression rules matching the same phone and domain
        phone = "+919876543210"
        domain = "acceptedgym0.com"
        await conn.execute("INSERT INTO suppression_list (phone_e164, reason) VALUES (%s, 'reason_1')", (phone,))
        await conn.execute("INSERT INTO suppression_list (phone_e164, reason) VALUES (%s, 'reason_2')", (phone,))
        await conn.execute("INSERT INTO suppression_list (domain, reason) VALUES (%s, 'reason_3')", (domain,))
        await conn.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as api:
        r = (await api.get(f"/api/runs/{seeded_run}/leads?decision=accepted&include_suppressed=true&limit=1000")).json()
        ids = [i["id"] for i in r["items"]]
        assert len(ids) == len(set(ids)), f"Suppression check duplicated rows: {len(ids)} vs {len(set(ids))}"


@pytest.mark.asyncio
async def test_no_null_decisions(seeded_run: str) -> None:
    """Invariant: decision column in run_results is strictly NOT NULL."""
    async with get_conn() as conn:
        row = await (await conn.execute(
            "SELECT count(*) AS count FROM run_results WHERE run_id = %s AND decision IS NULL",
            (seeded_run,),
        )).fetchone()
        assert row is not None
        count_val = row["count"] if "count" in row else list(row.values())[0]
        assert count_val == 0


@pytest.mark.asyncio
async def test_export_default_matches_visible_tab(seeded_run: str) -> None:
    """Invariant: default export matches the Accepted tab count."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as api:
        api_total = (await api.get(f"/api/runs/{seeded_run}/leads?decision=accepted&limit=1")).json()["total"]
        csv_rows = len((await api.get(f"/api/runs/{seeded_run}/export")).text.strip().splitlines()) - 1
        assert csv_rows == api_total, f"default export {csv_rows} != Accepted tab {api_total}"
