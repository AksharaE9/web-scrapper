import asyncio
import sys
import pytest_asyncio
from app.db import pool as db_pool

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest_asyncio.fixture(autouse=True, scope="session")
async def setup_db_pool():
    await db_pool.init_pools()
    yield
    try:
        await db_pool.close_pools()
    except Exception:
        pass

