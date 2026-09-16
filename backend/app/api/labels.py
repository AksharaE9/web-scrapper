"""Labels API — labelling queue, submit labels, add missed businesses."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from fastapi import APIRouter
from app.db.pool import get_conn

router = APIRouter(tags=["labels"])


@router.get("/labels/queue")
async def label_queue(run_id: str | None = None, limit: int = 30) -> dict[str, Any]:
    """
    Return a stratified sample of leads for labelling.
    Stratified across confidence tiers so calibration is measurable.
    Already-labelled leads are excluded.
    """
    async with get_conn() as conn:
        if run_id:
            # Stratified: ~10 from each tier
            rows = await (await conn.execute(
                """
                SELECT b.id, b.canonical_name, b.primary_category, b.phones_e164,
                       b.emails, b.website_url, b.address_text, b.tier, b.confidence,
                       rr.rank
                FROM run_results rr
                JOIN businesses b ON b.id = rr.business_id
                WHERE rr.run_id = %s
                  AND b.id NOT IN (
                    SELECT business_id FROM gold_labels
                    WHERE run_id = %s AND label_type = 'lead' AND business_id IS NOT NULL
                  )
                ORDER BY
                    CASE b.tier WHEN 'Likely' THEN 1 WHEN 'Verified' THEN 2 ELSE 3 END,
                    RANDOM()
                LIMIT %s
                """,
                (run_id, run_id, limit),
            )).fetchall()
        else:
            rows: list[Any] = []

    return {
        "queue": [dict(r) for r in rows],
        "count": len(rows),
    }


@router.post("/labels")
async def submit_label(body: dict[str, Any]) -> dict[str, str]:
    """Submit a single label verdict."""
    verdict = body.get("verdict") or body.get("label", "correct")
    async with get_conn() as conn:
        await conn.execute(
            """
            INSERT INTO gold_labels (business_id, run_id, label_type, label, notes)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                body.get("business_id"),
                body.get("run_id"),
                body.get("label_type", "lead"),
                verdict,
                body.get("notes", ""),
            ),
        )
        await conn.commit()
    return {"status": "ok"}


@router.post("/runs/{run_id}/missed")
async def add_missed_business(run_id: str, body: dict[str, Any]) -> dict[str, str]:
    """Add a missed business found by a reviewer (for recall measurement)."""
    async with get_conn() as conn:
        await conn.execute(
            "INSERT INTO missed_businesses (run_id, name, note) VALUES (%s, %s, %s)",
            (run_id, body["name"], body.get("note", "")),
        )
        await conn.commit()
    return {"status": "ok"}
