"""Celery task definitions for the analysis pipeline."""

from __future__ import annotations

import asyncio
from typing import Any

from langchain_core.runnables import RunnableConfig

from src.core.exceptions import KSAAgentError
from src.core.logging_setup import get_logger, setup_logging
from src.workers.celery_app import celery_app

logger = get_logger(__name__)


async def _run_pipeline_async(
    run_id: str,
    districts: list[str],
    max_listings_per_district: int,
    use_mock_data: bool,
) -> dict[str, Any]:
    """Async orchestrator for the full LangGraph pipeline.

    Initializes the database pool, builds and runs the graph, and
    closes the pool on completion or error.

    This function is the single async entry point called by
    asyncio.run() from the synchronous Celery task. All async
    operations (pool init, graph execution, pool teardown) are
    contained here to ensure proper event loop lifecycle.

    Args:
        run_id: Unique identifier for this pipeline run.
        districts: List of Riyadh districts to analyze.
        max_listings_per_district: Max listings per district.
        use_mock_data: Whether to use mock dataset.

    Returns:
        Dict with run_id, status, current_phase, investment_report,
        and error fields.
    """
    from src.core.database import close_pool, initialize_pool
    from src.core.state import AgentState
    from src.graph.builder import build_graph
    from src.mcp_servers.postgres_server.repository import ListingRepository

    logger.info(
        "Async pipeline orchestrator started",
        extra={"run_id": run_id, "districts": districts},
    )

    await initialize_pool()
    try:
        repo = ListingRepository()
        await repo.create_analysis_run(run_id)

        graph = build_graph()
        config: RunnableConfig = {"configurable": {"thread_id": run_id}}

        initial_state = AgentState(run_id=run_id, current_phase="initialized")

        async for state_snapshot in graph.astream(initial_state, config=config):
            for node_name, state_update in state_snapshot.items():
                logger.info(
                    "Pipeline node completed",
                    extra={
                        "run_id": run_id,
                        "node": node_name,
                        "phase": state_update.get("current_phase", "unknown"),
                    },
                )

        final_state_snapshot = graph.get_state(config)
        final_values = final_state_snapshot.values

        # Persist cleaned_listings to database
        cleaned_listings = final_values.get("cleaned_listings", [])
        if cleaned_listings:
            cleaned_dicts = []
            for listing in cleaned_listings:
                if hasattr(listing, "model_dump"):
                    cleaned_dicts.append(listing.model_dump())
                elif isinstance(listing, dict):
                    cleaned_dicts.append(listing)

            if cleaned_dicts:
                inserted = await repo.insert_cleaned_listings(
                    cleaned_dicts, run_id
                )
                logger.info(
                    "Cleaned listings persisted",
                    extra={
                        "run_id": run_id,
                        "inserted": inserted,
                        "total": len(cleaned_dicts),
                    }
                )

        # Persist compliance_flags to database
        compliance_flags = final_values.get("compliance_flags", [])
        if compliance_flags:
            flag_dicts = []
            for flag in compliance_flags:
                if hasattr(flag, "model_dump"):
                    flag_dicts.append(flag.model_dump())
                elif isinstance(flag, dict):
                    flag_dicts.append(flag)

            if flag_dicts:
                inserted_flags = await repo.insert_compliance_flags(
                    flag_dicts, run_id
                )
                logger.info(
                    "Compliance flags persisted",
                    extra={
                        "run_id": run_id,
                        "inserted": inserted_flags,
                        "total": len(flag_dicts),
                    }
                )

        # Also insert price history for time-series tracking
        for listing in cleaned_listings:
            try:
                if hasattr(listing, "price_per_sqm") and listing.price_per_sqm:
                    from datetime import datetime, timezone
                    await repo.insert_price_history(
                        listing_id=listing.listing_id,
                        district=listing.district or "",
                        price_sar=listing.price_sar or 0.0,
                        price_per_sqm=listing.price_per_sqm,
                        recorded_at=datetime.now(timezone.utc).isoformat(),
                    )
            except Exception as e:
                logger.warning(
                    "Price history insert failed for listing",
                    extra={
                        "listing_id": getattr(listing, "listing_id", "?"),
                        "error": str(e),
                    }
                )

        await repo.update_analysis_run(
            run_id=run_id,
            status="completed",
            summary=str(final_values.get("investment_report", ""))[:500],
            total_listings=len(final_values.get("cleaned_listings", [])),
        )

        logger.info("Pipeline completed successfully", extra={"run_id": run_id})

        return {
            "run_id": run_id,
            "status": "complete",
            "current_phase": final_values.get("current_phase", "complete"),
            "investment_report": final_values.get("investment_report", ""),
            "error": None,
        }

    except KSAAgentError as exc:
        logger.error(
            "Pipeline KSAAgentError", extra={"run_id": run_id, "error": str(exc)}
        )
        try:
            repo = ListingRepository()
            await repo.update_analysis_run(run_id=run_id, status="failed", summary=str(exc))
        except Exception:
            logger.error(
                "Failed to record run failure in database",
                exc_info=True,
                extra={"run_id": run_id},
            )
        return {
            "run_id": run_id,
            "status": "failed",
            "current_phase": "failed",
            "investment_report": None,
            "error": str(exc),
        }

    except Exception as exc:
        logger.error(
            "Pipeline unexpected error", exc_info=True, extra={"run_id": run_id}
        )
        return {
            "run_id": run_id,
            "status": "failed",
            "current_phase": "failed",
            "investment_report": None,
            "error": str(exc),
        }

    finally:
        await close_pool()


@celery_app.task(  # type: ignore[untyped-decorator]
    name="src.workers.tasks.run_analysis_pipeline",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def run_analysis_pipeline(
    self: Any,
    run_id: str,
    districts: list[str],
    max_listings_per_district: int = 10,
    use_mock_data: bool = True,
) -> dict[str, Any]:
    """Celery task: execute the full LangGraph analysis pipeline.

    Synchronous Celery task that wraps the async pipeline orchestrator
    using asyncio.run(). Each invocation creates a fresh event loop —
    correct for Celery worker threads, which have no pre-existing
    event loop.

    Args:
        self: Celery task instance (bind=True).
        run_id: Unique pipeline run identifier.
        districts: Riyadh districts to analyze.
        max_listings_per_district: Max listings per district.
        use_mock_data: Use mock data instead of live search.

    Returns:
        Pipeline result dict with status and report.
    """
    setup_logging()
    logger.info(
        "Celery task started", extra={"run_id": run_id, "task_id": self.request.id}
    )

    try:
        result = asyncio.run(
            _run_pipeline_async(
                run_id=run_id,
                districts=districts,
                max_listings_per_district=max_listings_per_district,
                use_mock_data=use_mock_data,
            )
        )
        return result

    except Exception as exc:
        logger.error(
            "Celery task failed, scheduling retry",
            exc_info=True,
            extra={"run_id": run_id},
        )
        raise self.retry(exc=exc, countdown=60)
