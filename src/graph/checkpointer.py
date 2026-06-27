"""LangGraph state checkpointer configuration.

Provides AsyncPostgresSaver for production runs and MemorySaver for
development/testing without a database.
"""

from __future__ import annotations

import os
from contextlib import AbstractAsyncContextManager

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from src.core.config import get_settings
from src.core.exceptions import DataLayerError
from src.core.logging_setup import get_logger

logger = get_logger(__name__)


def get_memory_checkpointer() -> MemorySaver:
    """Return an in-memory checkpointer for testing.

    Used in unit tests and graph compilation checks where no database
    connection is available.

    Returns:
        MemorySaver instance with no persistence.
    """
    logger.info("Using MemorySaver checkpointer (dev/test mode)")
    return MemorySaver()


def get_postgres_checkpointer() -> AbstractAsyncContextManager[AsyncPostgresSaver]:
    """Return an AsyncPostgresSaver context manager for production runs.

    Connects to PostgreSQL using POSTGRES_URL from settings. The
    returned object must be entered with ``async with`` by the caller,
    which also handles creating checkpointing tables on first use via
    ``checkpointer.setup()``.

    Returns:
        Async context manager yielding an AsyncPostgresSaver connected
        to PostgreSQL.

    Raises:
        DataLayerError: If the connection string cannot be resolved.
    """
    try:
        settings = get_settings()
        postgres_url = settings.postgres_url.get_secret_value()
        checkpointer_cm = AsyncPostgresSaver.from_conn_string(postgres_url)
        logger.info("AsyncPostgresSaver checkpointer context manager created")
        return checkpointer_cm
    except Exception as exc:
        logger.error(
            "Failed to initialize postgres checkpointer", extra={"error": str(exc)}
        )
        raise DataLayerError(
            "Postgres checkpointer initialization failed",
            context={"error": str(exc)},
        ) from exc


def get_checkpointer() -> MemorySaver:
    """Return the appropriate checkpointer based on environment.

    Production: the Celery task's async orchestrator uses
    get_postgres_checkpointer() directly inside its own event loop,
    since AsyncPostgresSaver must be entered as an async context
    manager. Development/testing: returns MemorySaver here, used by
    synchronous callers such as graph compilation checks.

    Returns:
        MemorySaver for non-production environments and synchronous
        callers.
    """
    app_env = os.getenv("APP_ENV", "development")
    if app_env == "development":
        return get_memory_checkpointer()
    return get_memory_checkpointer()
