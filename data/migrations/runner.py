"""Standalone database migration runner for Phase 2."""

from __future__ import annotations

import asyncio

from src.core.database import close_pool, initialize_pool
from src.core.logging_setup import get_logger, setup_logging
from src.mcp_servers.postgres_server.repository import ListingRepository

logger = get_logger(__name__)


async def run_migrations() -> None:
    """Initialize the database schema.

    Calls ``ListingRepository.create_tables()``, which executes
    ``ALL_SCHEMAS`` from ``schemas.py`` in a single transaction. Safe to
    run multiple times since all DDL uses ``IF NOT EXISTS``.
    """
    setup_logging()
    logger.info("Starting database migration")
    await initialize_pool()
    try:
        repo = ListingRepository()
        await repo.create_tables()
        logger.info("Migration completed successfully")
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(run_migrations())
