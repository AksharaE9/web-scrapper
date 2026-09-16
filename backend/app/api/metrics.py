"""Metrics API — ground-truth and proxy metrics per run and globally."""
from __future__ import annotations
from typing import Any
from fastapi import APIRouter, HTTPException
from app.db.pool import get_conn

router = APIRouter(tags=["metrics"])


@router.get("/metrics/runs/{run_id}")
async def run_metrics(run_id: str) -> dict[str, Any]:
    async with get_conn() as conn:
        snaps = await (await conn.execute(
            "SELECT * FROM metrics_snapshots WHERE run_id = %s ORDER BY computed_at DESC",
            (run_id,),
        )).fetchall()
        label_count = await (await conn.execute(
            "SELECT COUNT(*) AS n FROM gold_labels WHERE run_id = %s AND label_type = 'lead'",
            (run_id,),
        )).fetchone()

    n = label_count["n"] if label_count else 0
    metrics = [dict(s) for s in snaps]
    return {
        "run_id": run_id,
        "label_count": n,
        "labels_needed_for_ground_truth": max(0, 30 - n),
        "metrics": metrics,
    }


@router.get("/metrics/global")
async def global_metrics() -> dict[str, Any]:
    async with get_conn() as conn:
        snaps = await (await conn.execute(
            "SELECT * FROM metrics_snapshots WHERE run_id IS NULL ORDER BY computed_at DESC LIMIT 50",
        )).fetchall()
    return {"metrics": [dict(s) for s in snaps]}
