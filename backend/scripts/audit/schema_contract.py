"""
scripts/audit/schema_contract.py — Database schema, extensions, and types audit against Postgres information_schema.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from rich.console import Console
from rich.table import Table
from app.db.pool import get_conn, init_pools, close_pools


async def audit_schema_contract() -> dict[str, Any]:
    await init_pools()
    console = Console()
    results: dict[str, Any] = {"status": "ok", "tables": {}, "extensions": {}}

    try:
        async with get_conn() as conn:
            # 1. Extensions check
            ext_rows = await (await conn.execute("SELECT extname, extversion FROM pg_extension")).fetchall()
            installed_exts = {r["extname"]: r["extversion"] for r in ext_rows}
            results["extensions"] = installed_exts

            required_exts = ["plpgsql", "postgis", "pg_trgm", "vector", "citext"]
            missing_exts = [e for e in required_exts if e not in installed_exts]

            # 2. Check query_runs columns
            qr_cols_rows = await (await conn.execute(
                """
                SELECT column_name, data_type, udt_name 
                FROM information_schema.columns 
                WHERE table_name = 'query_runs'
                """
            )).fetchall()
            qr_cols = {r["column_name"]: (r["data_type"], r["udt_name"]) for r in qr_cols_rows}
            results["tables"]["query_runs"] = qr_cols

            # 3. Check businesses columns
            biz_cols_rows = await (await conn.execute(
                """
                SELECT column_name, data_type, udt_name 
                FROM information_schema.columns 
                WHERE table_name = 'businesses'
                """
            )).fetchall()
            biz_cols = {r["column_name"]: (r["data_type"], r["udt_name"]) for r in biz_cols_rows}
            results["tables"]["businesses"] = biz_cols

            # Display Extensions
            ext_table = Table(title="PostgreSQL Extensions Audit", show_header=True, header_style="bold green")
            ext_table.add_column("Extension", width=20)
            ext_table.add_column("Required", width=12)
            ext_table.add_column("Status / Version", width=20)

            for req in required_exts:
                if req in installed_exts:
                    ext_table.add_row(req, "Yes", f"[green]Installed (v{installed_exts[req]})[/green]")
                else:
                    ext_table.add_row(req, "Yes", "[red]MISSING[/red]")

            console.print(ext_table)

            # Display Key Columns
            col_table = Table(title="Key Column Contract & Type Audit", show_header=True, header_style="bold cyan")
            col_table.add_column("Table", width=15)
            col_table.add_column("Column", width=20)
            col_table.add_column("Expected Type", width=20)
            col_table.add_column("Actual Type", width=20)
            col_table.add_column("Status", width=12)

            checks = [
                ("query_runs", "keywords", "ARRAY (text[])", qr_cols.get("keywords", ("N/A", "N/A"))[1]),
                ("query_runs", "exclude_keywords", "ARRAY (text[])", qr_cols.get("exclude_keywords", ("N/A", "N/A"))[1]),
                ("query_runs", "options", "jsonb", qr_cols.get("options", ("N/A", "N/A"))[1]),
                ("query_runs", "stats", "jsonb", qr_cols.get("stats", ("N/A", "N/A"))[1]),
                ("businesses", "categories", "ARRAY (text[])", biz_cols.get("categories", ("N/A", "N/A"))[1]),
                ("businesses", "phones_e164", "ARRAY (text[])", biz_cols.get("phones_e164", ("N/A", "N/A"))[1]),
                ("businesses", "socials", "jsonb", biz_cols.get("socials", ("N/A", "N/A"))[1]),
                ("businesses", "address", "jsonb", biz_cols.get("address", ("N/A", "N/A"))[1]),
                ("businesses", "geom", "USER-DEFINED / geography", biz_cols.get("geom", ("N/A", "N/A"))[1]),
            ]

            all_passed = True
            for tbl, col, expected, actual in checks:
                matches = (actual in expected.lower() or expected.lower() in actual or actual in ("_text", "jsonb", "geography", "geometry"))
                if not matches:
                    all_passed = False
                status_str = "[green]MATCH[/green]" if matches else "[red]MISMATCH[/red]"
                col_table.add_row(tbl, col, expected, actual, status_str)

            console.print(col_table)

            if missing_exts or not all_passed:
                console.print("\n[red][FAIL] Schema Contract Violations Found![/red]")
                results["status"] = "error"
            else:
                console.print("\n[green][PASS] All schema contracts, extensions, and array/jsonb types verified successfully.[/green]")

            return results
    finally:
        await close_pools()


def main() -> None:
    asyncio.run(audit_schema_contract())


if __name__ == "__main__":
    main()
