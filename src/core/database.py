"""Manages the asyncpg connection pool singleton for PostgreSQL access."""

from __future__ import annotations

import asyncpg

from src.core.config import get_settings
from src.core.exceptions import DataLayerError
from src.core.logging_setup import get_logger

logger = get_logger(__name__)

_pool: asyncpg.Pool | None = None


async def initialize_pool() -> None:
    """Initialize the asyncpg connection pool.

    Creates a pool with ``min_size=2`` and ``max_size=10`` using the
    ``POSTGRES_URL`` configured in application settings. Must be called
    once at application startup before any repository operation runs.

    Raises:
        DataLayerError: If the connection pool cannot be created, with
            the original exception captured in the error context.
    """
    global _pool
    settings = get_settings()
    try:
        _pool = await asyncpg.create_pool(
            dsn=settings.postgres_url.get_secret_value(),
            min_size=2,
            max_size=10,
        )
    except Exception as exc:
        logger.error("Failed to initialize connection pool", exc_info=True)
        raise DataLayerError(
            "Failed to initialize database connection pool",
            context={"error": str(exc)},
        ) from exc
    logger.info("Connection pool initialized with min_size=2 max_size=10")


async def close_pool() -> None:
    """Gracefully close the connection pool, if one is open.

    Safe to call even if ``initialize_pool`` was never called.
    """
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("Connection pool closed")


def get_pool() -> asyncpg.Pool:
    """Return the active connection pool.

    Returns:
        The module-level asyncpg connection pool.

    Raises:
        DataLayerError: If the pool has not been initialized yet.
    """
    if _pool is None:
        raise DataLayerError(
            "Connection pool not initialized. Call initialize_pool() first."
        )
    return _pool


async def health_check() -> dict[str, str]:
    """Run a lightweight database health check.

    Returns:
        A dict with ``{"status": "healthy", "version": "<pg version>"}``
        on success, or ``{"status": "unhealthy", "error": "<message>"}``
        on failure. This function never raises.
    """
    try:
        pool = get_pool()
        version = await pool.fetchval("SELECT version()")
        return {"status": "healthy", "version": str(version)}
    except Exception as exc:
        logger.error("Database health check failed", exc_info=True)
        return {"status": "unhealthy", "error": str(exc)}
