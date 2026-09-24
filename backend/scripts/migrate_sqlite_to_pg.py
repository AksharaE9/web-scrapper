"""
Script to archive legacy SQLite database (data/leadcore.db) to data/_archive/
and migrate any valid seed records into PostgreSQL if requested.
"""

import shutil
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migrate_sqlite")

DATA_DIR = Path(__file__).parent.parent / "data"
SQLITE_DB = DATA_DIR / "leadcore.db"
ARCHIVE_DIR = DATA_DIR / "_archive"


def archive_sqlite_db() -> None:
    if not SQLITE_DB.exists():
        logger.info("No sqlite database found at %s. Nothing to archive.", SQLITE_DB)
        return

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    target = ARCHIVE_DIR / f"leadcore_legacy_{SQLITE_DB.stat().st_mtime_ns}.db"
    shutil.move(str(SQLITE_DB), str(target))
    logger.info("Archived legacy SQLite database to %s", target)


if __name__ == "__main__":
    archive_sqlite_db()
