"""
scripts/audit/why_failed.py — Query and pretty-print recent run statuses and errors.

Usage:
  python scripts/audit/why_failed.py [--last N] [--run-id UUID]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from rich.console import Console
from rich.table import Table

from app.db.pool import get_conn, init_pools, close_pools


async def query_run_failures(last_n: int = 20, run_id: str | None = None) -> None:
    await init_pools()
    console = Console()

    table = Table(title=f"LeadCore Zero — Recent Runs Audit (Limit: {last_n})", show_header=True, header_style="bold magenta")
    table.add_column("Run ID", style="dim", width=12)
    table.add_column("Created At", width=19)
    table.add_column("Status", width=10)
    table.add_column("Locality / City", width=22)
    table.add_column("Keywords", width=20)
    table.add_column("Leads", justify="right", width=6)
    table.add_column("Error / Failure Summary", width=40)

    try:
        async with get_conn() as conn:
            if run_id:
                query = "SELECT id, created_at, status, locality, city, keywords, error, stats FROM query_runs WHERE id = %s"
                params = (run_id,)
            else:
                query = "SELECT id, created_at, status, locality, city, keywords, error, stats FROM query_runs ORDER BY created_at DESC LIMIT %s"
                params = (last_n,)

            rows = await (await conn.execute(query, params)).fetchall()

            for r in rows:
                d = dict(r)
                rid = str(d["id"])[:8] + "..."
                created = d["created_at"].strftime("%Y-%m-%d %H:%M:%S") if isinstance(d["created_at"], datetime) else str(d["created_at"])[:19]
                status = str(d["status"]).upper()
                loc = f"{d.get('locality') or ''}, {d.get('city') or ''}".strip(", ") or "N/A"
                kws = ", ".join(d.get("keywords") or []) if isinstance(d.get("keywords"), list) else str(d.get("keywords") or "")

                # Stats / leads count
                stats_raw = d.get("stats")
                stats_dict = stats_raw if isinstance(stats_raw, dict) else (json.loads(stats_raw) if stats_raw and isinstance(stats_raw, str) else {})
                leads = str(stats_dict.get("resolved_entity_count", stats_dict.get("candidate_count", 0)))

                # Status color
                status_colored = f"[green]{status}[/green]" if status in ("COMPLETED", "PARTIAL") else (f"[yellow]{status}[/yellow]" if status in ("RUNNING", "QUEUED") else f"[red]{status}[/red]")

                err = d.get("error") or ""
                if isinstance(err, str) and err.startswith("{"):
                    try:
                        err_parsed = json.loads(err)
                        err = f"[{err_parsed.get('node', 'node')}] {err_parsed.get('message', err)}"
                    except Exception:
                        pass
                err_summary = (err[:38] + "...") if len(err) > 40 else (err or "[green]None (OK)[/green]")

                table.add_row(rid, created, status_colored, loc, kws[:20], leads, err_summary)

        console.print(table)
    finally:
        await close_pools()


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit LeadCore Zero Run Failures")
    parser.add_argument("--last", type=int, default=15, help="Number of recent runs to display")
    parser.add_argument("--run-id", type=str, default=None, help="Inspect a specific run ID")
    args = parser.parse_args()

    asyncio.run(query_run_failures(last_n=args.last, run_id=args.run_id))


if __name__ == "__main__":
    main()
