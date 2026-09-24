"""
Cache Garbage Collection Script — LeadCore Zero

Scans overture cache directory, purges files older than max_age_days or orphan sidecars,
and reports total storage freed.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

from app.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cache_gc")


def prune_cache(max_age_days: int = 60, dry_run: bool = False) -> dict[str, int]:
    cache_dir = settings.overture_cache_dir
    if not cache_dir.exists():
        logger.info(f"Cache directory {cache_dir} does not exist. Nothing to prune.")
        return {"deleted_files": 0, "freed_bytes": 0}

    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    deleted_files = 0
    freed_bytes = 0

    for parquet_file in cache_dir.rglob("*.parquet"):
        meta_file = parquet_file.with_suffix(".meta.json")
        is_expired = False

        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                written_at_str = meta.get("written_at")
                if written_at_str:
                    written_at = datetime.fromisoformat(written_at_str)
                    if written_at.tzinfo is None:
                        written_at = written_at.replace(tzinfo=timezone.utc)
                    if written_at < cutoff:
                        is_expired = True
            except Exception:
                is_expired = True
        else:
            # Check filesystem mtime
            mtime = datetime.fromtimestamp(parquet_file.stat().st_mtime, timezone.utc)
            if mtime < cutoff:
                is_expired = True

        if is_expired:
            file_size = parquet_file.stat().st_size
            meta_size = meta_file.stat().st_size if meta_file.exists() else 0
            freed_bytes += file_size + meta_size
            deleted_files += 1 if not meta_file.exists() else 2

            if not dry_run:
                parquet_file.unlink(missing_ok=True)
                if meta_file.exists():
                    meta_file.unlink(missing_ok=True)
                logger.info(f"Deleted expired cache: {parquet_file.name} ({file_size / 1024:.1f} KB)")
            else:
                logger.info(f"[DRY-RUN] Would delete: {parquet_file.name} ({file_size / 1024:.1f} KB)")

    logger.info(f"Cache GC complete. Deleted {deleted_files} files, freed {freed_bytes / (1024 * 1024):.2f} MB.")
    return {"deleted_files": deleted_files, "freed_bytes": freed_bytes}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Purge stale Overture cache files")
    parser.add_argument("--max-age-days", type=int, default=60, help="Maximum allowed cache age in days")
    parser.add_argument("--dry-run", action="store_true", help="Report without deleting files")
    args = parser.parse_args()

    prune_cache(max_age_days=args.max_age_days, dry_run=args.dry_run)
