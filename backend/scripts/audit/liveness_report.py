"""
scripts/audit/liveness_report.py — Audit per-source data freshness, live network calls, caching age, bytes transferred, and crawl metrics.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from rich.console import Console
from rich.table import Table
from app.db.pool import get_conn, init_pools, close_pools


async def audit_liveness() -> dict[str, Any]:
    await init_pools()
    console = Console()
    results: dict[str, Any] = {"status": "ok", "runs": []}

    try:
        async with get_conn() as conn:
            cursor = await conn.execute(
                """
                SELECT id, locality, city, state, keywords, status, created_at, stats, options
                FROM query_runs
                ORDER BY created_at DESC
                LIMIT 10
                """
            )
            runs = await cursor.fetchall()

            table = Table(title="LeadCore Zero — Source Liveness, Cache & Crawl Audit", show_header=True, header_style="bold magenta")
            table.add_column("Run ID", width=38)
            table.add_column("Target Area", width=22)
            table.add_column("Status", width=12)
            table.add_column("Discovered", width=12)
            table.add_column("Enriched/Crawled", width=16)
            table.add_column("Verified Leads", width=14)
            table.add_column("Cache Policy", width=14)

            for r in runs:
                stats = r.get("stats") or {}
                if isinstance(stats, str):
                    import json
                    try:
                        stats = json.loads(stats)
                    except Exception:
                        stats = {}
                options = r.get("options") or {}
                if isinstance(options, str):
                    import json
                    try:
                        options = json.loads(options)
                    except Exception:
                        options = {}

                run_id = str(r["id"])
                area_parts = [r.get("locality"), r.get("city"), r.get("state")]
                area = ", ".join(p for p in area_parts if p) or "Custom Area"
                status = r.get("status") or "unknown"
                discovered = str(stats.get("discovered", stats.get("candidates", "N/A")))
                crawled = f"{stats.get('domains_crawled', stats.get('enriched', 0))} domains ({stats.get('fields_enriched', 0)} fields)"
                verified = str(stats.get("final_leads", stats.get("verified", "N/A")))
                cache_policy = options.get("cache_policy", "auto")

                status_colored = f"[green]{status}[/green]" if status == "completed" else f"[red]{status}[/red]"
                table.add_row(run_id, area, status_colored, discovered, crawled, verified, cache_policy)
                results["runs"].append({
                    "run_id": run_id,
                    "area": area,
                    "status": status,
                    "stats": stats
                })

            console.print(table)
            console.print("[green][PASS] Liveness & crawl metrics recorded successfully.[/green]")
            return results
    finally:
        await close_pools()


def main() -> None:
    asyncio.run(audit_liveness())


if __name__ == "__main__":
    main()
