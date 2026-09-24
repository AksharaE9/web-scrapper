"""
tests/e2e/conftest.py

Psycopg in async mode on Windows requires SelectorEventLoop.
"""
import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
