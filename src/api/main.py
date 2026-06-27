"""FastAPI application entry point."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes.analysis import router as analysis_router
from src.api.routes.listings import router as listings_router
from src.api.schemas import HealthResponse
from src.core.config import get_settings
from src.core.logging_setup import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifespan — startup and shutdown.

    Startup: initialize database connection pool. Shutdown:
    gracefully close connection pool. Uses the lifespan context
    manager (FastAPI 0.93+ standard) over deprecated @app.on_event
    decorators.

    Args:
        app: The FastAPI application instance.

    Yields:
        None. The application runs while this generator is suspended.
    """
    from src.core.database import close_pool, initialize_pool

    logger.info("Application startup initiated")
    try:
        await initialize_pool()
        logger.info("Application startup complete")
    except Exception:
        logger.error("Startup failed — database unavailable", exc_info=True)
        # Allow app to start in degraded mode; /health reports the
        # database as unhealthy rather than crashing the process.

    yield

    logger.info("Application shutdown initiated")
    await close_pool()
    logger.info("Application shutdown complete")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application with all routers and
        middleware registered.
    """
    settings = get_settings()

    app = FastAPI(
        title="KSA Real Estate Investment Agent",
        description=(
            "Multi-agent AI pipeline for Riyadh real estate "
            "market intelligence and investment analysis"
        ),
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(analysis_router)
    app.include_router(listings_router)

    @app.get("/health", response_model=HealthResponse, tags=["system"])
    async def health_check() -> HealthResponse:
        """System health check endpoint.

        Verifies database and Redis connectivity. Used by Docker
        Compose and Render.com health checks.

        Returns:
            HealthResponse with per-service status.
        """
        from redis import Redis

        from src.core.database import health_check as db_health

        db_result = await db_health()
        db_status = db_result.get("status", "unhealthy")

        try:
            redis_client = Redis.from_url(settings.redis_url, socket_connect_timeout=2)
            redis_client.ping()
            redis_status = "healthy"
        except Exception:
            redis_status = "unhealthy"

        overall: str = (
            "healthy"
            if db_status == "healthy" and redis_status == "healthy"
            else "degraded"
        )

        return HealthResponse(
            status=overall,  # type: ignore[arg-type]
            database=db_status,
            redis=redis_status,
        )

    @app.get("/", tags=["system"])
    async def root() -> dict[str, str]:
        """Root endpoint — confirms the API is running."""
        return {
            "service": "KSA Real Estate Investment Agent",
            "version": "0.1.0",
            "docs": "/docs",
        }

    logger.info("FastAPI application created", extra={"env": settings.app_env})
    return app


app = create_app()
