"""N3e — ImportAgent (user CSV imports from data/imports/)."""
from __future__ import annotations
import csv
from pathlib import Path
from datetime import datetime, timezone
from typing import Any
from app.graph.runtime import node
from app.graph.state import RawCandidate, RunState
from app.settings import settings


@node("n3e_imports", critical=False, max_retries=1)
async def run(state: RunState) -> dict[str, Any]:
    imports_dir = settings.data_dir / "imports"
    candidates: list[RawCandidate] = []

    for csv_file in imports_dir.glob("*.csv"):
        try:
            with open(csv_file, encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    name = row.get("name") or row.get("Name") or row.get("business_name")
                    if not name:
                        continue
                    try:
                        lon = float(row.get("lon") or row.get("longitude") or 0)
                        lat = float(row.get("lat") or row.get("latitude") or 0)
                    except ValueError:
                        continue
                    if not lon or not lat:
                        continue

                    candidates.append(RawCandidate(
                        source=f"import:{csv_file.name}",
                        source_record_id=f"{csv_file.name}:{row.get('id', name)}",
                        source_lineage=["user_import"],
                        name=name,
                        lon=lon,
                        lat=lat,
                        categories=[row.get("category", "")],
                        phones=[row.get("phone", "")],
                        emails=[row.get("email", "")],
                        websites=[row.get("website", "")],
                        address={"street": row.get("address", "")},
                        licence=f"import:{csv_file.name}",
                        fetched_at=datetime.now(timezone.utc),
                        raw=dict(row),
                    ))
        except Exception:
            pass

    return {
        "raw_candidates": candidates,
        "source_stats": {"imports": {"count": len(candidates)}},
    }
