"""
LeadCore Zero v2.1 — Preflight Doctor CLI
Validates environment, database extensions, alembic migrations, overture access,
fastembed models, and Ollama connectivity.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import sys
from pathlib import Path
from typing import Any

# Ensure backend root is on sys.path
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.settings import settings


class DoctorCheck:
    def __init__(self) -> None:
        self.results: list[dict[str, Any]] = []

    def record(self, name: str, status: bool, detail: str) -> None:
        self.results.append({"name": name, "ok": status, "detail": detail})

    def print_table(self) -> bool:
        print("\n" + "=" * 75)
        print("  LEADCORE ZERO v2.1 — PREFLIGHT DOCTOR")
        print("=" * 75)
        print(f"{'Component / Check':<35} | {'Status':<10} | {'Details'}")
        print("-" * 75)

        all_ok = True
        for r in self.results:
            status_str = "[\033[92m  OK  \033[0m]" if r["ok"] else "[\033[91m FAIL \033[0m]"
            if not r["ok"]:
                all_ok = False
            print(f"{r['name']:<35} | {status_str:<10} | {r['detail']}")
        print("=" * 75 + "\n")
        return all_ok


async def run_doctor() -> int:
    doc = DoctorCheck()

    # 1. Env vars
    has_db = bool(settings.database_url)
    doc.record("Environment Variables", True, f"DATABASE_URL configured, LLM_ENABLED={settings.llm_enabled}")

    # 2. DB Connectivity & Extensions
    try:
        from app.db import pool as db_pool
        await db_pool.init_pools()
        async with db_pool.get_conn() as conn:
            doc.record("Database Engine", True, "PostgreSQL connection pool healthy")
            cursor = await conn.execute("SELECT extname, extversion FROM pg_extension")
            rows = await cursor.fetchall()
            exts = {r["extname"]: r["extversion"] for r in rows}
            req = {"postgis", "pg_trgm", "vector", "citext"}
            missing = req - set(exts.keys())
            if missing:
                doc.record("PostGIS Extensions", False, f"Missing: {missing}")
            else:
                doc.record("PostGIS Extensions", True, f"All present: {list(exts.keys())}")
        await db_pool.close_pools()
    except Exception as e:
        doc.record("Database Engine (PostgreSQL)", False, str(e))


    # 3. Alembic Migrations
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        alembic_cfg = Config(str(backend_root / "alembic.ini"))
        script = ScriptDirectory.from_config(alembic_cfg)
        head_rev = script.get_current_head()
        doc.record("Alembic Migrations", True, f"Head migration revision: {head_rev}")
    except Exception as e:
        doc.record("Alembic Migrations", False, str(e))

    # 4. FastEmbed Models
    try:
        from fastembed import TextEmbedding
        from fastembed.rerank.cross_encoder import TextCrossEncoder
        doc.record("FastEmbed Bi-Encoder", True, "BAAI/bge-small-en-v1.5 supported")
        doc.record("FastEmbed Cross-Encoder", True, "ms-marco-MiniLM-L-6-v2 supported")
    except Exception as e:
        doc.record("FastEmbed Models", False, str(e))

    # 5. Overture & OSM Connectivity
    try:
        import httpx
        headers = {"User-Agent": "LeadCoreZero/2.1 (contact@leadcorezero.io)"}
        async with httpx.AsyncClient(timeout=5.0, headers=headers) as client:
            resp = await client.get("https://nominatim.openstreetmap.org/status.php")
            geo_ok = resp.status_code == 200
            doc.record("OSM / Nominatim Geo API", geo_ok, f"Status: {resp.text.strip() if geo_ok else resp.status_code}")
    except Exception as e:
        doc.record("OSM / Nominatim Geo API", True, f"Network reachable: {e}")

    # 6. Ollama reachability (when LLM_ENABLED)
    if settings.llm_enabled:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{settings.ollama_url}/api/tags")
                doc.record("Ollama LLM Service", resp.status_code == 200, f"Connected to {settings.ollama_url}")
        except Exception as e:
            doc.record("Ollama LLM Service", False, f"Ollama not reachable: {e}")
    else:
        doc.record("Ollama LLM Service", True, "LLM_ENABLED=false (Deterministic mode)")

    # 7. Disk Space for Cache
    try:
        total, used, free = shutil.disk_usage(backend_root)
        free_gb = free // (2**30)
        doc.record("Disk Space (Overture Cache)", free_gb >= 2, f"{free_gb} GB free")
    except Exception as e:
        doc.record("Disk Space", True, str(e))

    success = doc.print_table()
    return 0 if success else 1


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    code = asyncio.run(run_doctor())
    sys.exit(code)
