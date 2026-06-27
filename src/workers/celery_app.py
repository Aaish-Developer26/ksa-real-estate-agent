"""Celery application factory and configuration."""

from __future__ import annotations

from celery import Celery

from src.core.config import get_settings
from src.core.logging_setup import get_logger

logger = get_logger(__name__)


def create_celery_app() -> Celery:
    """Create and configure the Celery application.

    Reads broker and backend URLs from settings. Configures task
    serialization, timezone, and result expiry.

    Returns:
        Configured Celery application instance.
    """
    settings = get_settings()

    app = Celery(
        "ksa_re_agent",
        broker=settings.redis_url,
        backend=settings.redis_url,
    )

    app.conf.update(
        include=["src.workers.tasks"],
        # Serialization
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        # Timezone
        timezone="Asia/Riyadh",
        enable_utc=True,
        # Results
        result_expires=86400,  # 24 hours in seconds
        result_persistent=True,
        # Reliability
        task_acks_late=True,  # ack only after task completes
        task_reject_on_worker_lost=True,
        # Retry behavior
        task_max_retries=3,
        # Worker
        worker_prefetch_multiplier=1,  # one task at a time per worker
    )

    logger.info("Celery application configured", extra={"broker": settings.redis_url})
    return app


# Module-level singleton — imported by tasks.py and FastAPI
celery_app = create_celery_app()
