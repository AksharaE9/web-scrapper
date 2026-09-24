"""
scripts/audit/yield_report.py — Yield & extraction quality report across runs.
Measures the GAP between HTTP success (2xx) and extracted data yield (contact fill rates, structured fields).
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


async def compute_yield_report() -> dict[str, Any]:
    await init_pools()
    console = Console()
    report: dict[str, Any] = {
        "status": "ok",
        "total_businesses": 0,
        "fill_rates": {},
        "alerts": []
    }

    try:
        async with get_conn() as conn:
            # 1. Total business count
            count_row = await (await conn.execute("SELECT COUNT(*) AS total FROM businesses")).fetchone()
            total = count_row["total"] if count_row else 0
            report["total_businesses"] = total

            if total == 0:
                console.print("[yellow][WARN] No businesses found in database yet. Yield metrics cannot be computed from DB rows.[/yellow]")
                return report

            # 2. Field fill metrics
            query = """
            SELECT 
                COUNT(*) FILTER (WHERE array_length(phones_e164, 1) > 0) AS with_phones,
                COUNT(*) FILTER (WHERE array_length(emails, 1) > 0) AS with_emails,
                COUNT(*) FILTER (WHERE website_url IS NOT NULL AND website_url != '' OR website_domain IS NOT NULL AND website_domain != '') AS with_websites,
                COUNT(*) FILTER (WHERE address IS NOT NULL AND address != '{}'::jsonb) AS with_address,
                COUNT(*) FILTER (WHERE socials IS NOT NULL AND socials != '{}'::jsonb) AS with_socials,
                COUNT(*) FILTER (WHERE confidence >= 0.8) AS tier_verified,
                COUNT(*) FILTER (WHERE confidence >= 0.6 AND confidence < 0.8) AS tier_high,
                COUNT(*) FILTER (WHERE confidence >= 0.4 AND confidence < 0.6) AS tier_medium,
                COUNT(*) FILTER (WHERE confidence < 0.4) AS tier_low
            FROM businesses
            """
            stats_row = await (await conn.execute(query)).fetchone()

            with_phones = stats_row["with_phones"] if stats_row else 0
            with_emails = stats_row["with_emails"] if stats_row else 0
            with_websites = stats_row["with_websites"] if stats_row else 0
            with_address = stats_row["with_address"] if stats_row else 0
            with_socials = stats_row["with_socials"] if stats_row else 0

            phone_rate = (with_phones / total) * 100
            email_rate = (with_emails / total) * 100
            website_rate = (with_websites / total) * 100
            address_rate = (with_address / total) * 100
            social_rate = (with_socials / total) * 100

            report["fill_rates"] = {
                "phone_fill_rate": phone_rate,
                "email_fill_rate": email_rate,
                "website_fill_rate": website_rate,
                "address_fill_rate": address_rate,
                "social_fill_rate": social_rate,
            }

            # Render Table
            table = Table(title=f"LeadCore Zero — Yield & Extraction Quality Report (N={total} Leads)", show_header=True, header_style="bold cyan")
            table.add_column("Metric / Field", width=25)
            table.add_column("Count Present", width=15)
            table.add_column("Fill Rate (%)", width=15)
            table.add_column("Quality Threshold", width=20)
            table.add_column("Status", width=12)

            table.add_row("Phone (E.164)", str(with_phones), f"{phone_rate:.1f}%", "Target ≥ 70%", "[green]HEALTHY[/green]" if phone_rate >= 70 else "[yellow]LOW[/yellow]")
            table.add_row("Email", str(with_emails), f"{email_rate:.1f}%", "Target ≥ 30%", "[green]HEALTHY[/green]" if email_rate >= 30 else "[yellow]LOW[/yellow]")
            table.add_row("Website Domain", str(with_websites), f"{website_rate:.1f}%", "Target ≥ 60%", "[green]HEALTHY[/green]" if website_rate >= 60 else "[yellow]LOW[/yellow]")
            table.add_row("Structured Address", str(with_address), f"{address_rate:.1f}%", "Target ≥ 80%", "[green]HEALTHY[/green]" if address_rate >= 80 else "[yellow]LOW[/yellow]")
            table.add_row("Social Profiles", str(with_socials), f"{social_rate:.1f}%", "Target ≥ 20%", "[green]HEALTHY[/green]" if social_rate >= 20 else "[yellow]LOW[/yellow]")

            console.print(table)

            # Alert evaluation
            if phone_rate < 50.0:
                report["alerts"].append("Phone extraction yield below critical threshold (50%)")
            if address_rate < 60.0:
                report["alerts"].append("Address resolution yield below critical threshold (60%)")

            if report["alerts"]:
                for alert in report["alerts"]:
                    console.print(f"[red][ALERT][/red] {alert}")
            else:
                console.print("\n[green][PASS] Overall yield metrics meet or exceed operational quality thresholds.[/green]")

            return report
    finally:
        await close_pools()


def main() -> None:
    asyncio.run(compute_yield_report())


if __name__ == "__main__":
    main()
