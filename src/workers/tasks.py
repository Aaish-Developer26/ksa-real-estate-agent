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
        raw_values = final_state_snapshot.values

        # Handle both Pydantic BaseModel and dict state
        # AgentState is a Pydantic BaseModel — use attribute
        # access, not .get()
        if hasattr(raw_values, 'model_dump'):
            # Pydantic BaseModel — convert to dict first
            final_values = raw_values.model_dump()
        elif isinstance(raw_values, dict):
            final_values = raw_values
        else:
            # Fallback — try both access patterns
            final_values = {}
            for field in [
                'investment_report', 'current_phase',
                'cleaned_listings', 'compliance_flags',
                'raw_listings', 'analysis_summary',
                'district_benchmarks', 'undervalued_listing_ids',
                'errors',
            ]:
                try:
                    final_values[field] = getattr(raw_values, field, None)
                except Exception:
                    pass

        logger.info(
            "Final state extracted",
            extra={
                "run_id": run_id,
                "phase": final_values.get("current_phase", "unknown"),
                "cleaned_count": len(
                    final_values.get("cleaned_listings", [])
                ),
                "has_report": bool(
                    final_values.get("investment_report")
                ),
            }
        )

        # Persist cleaned_listings to database
        cleaned_listings_raw = final_values.get("cleaned_listings", [])
        cleaned_listings = []
        for item in cleaned_listings_raw:
            if hasattr(item, 'model_dump'):
                cleaned_listings.append(item.model_dump())
            elif isinstance(item, dict):
                cleaned_listings.append(item)

        if cleaned_listings:
            inserted = await repo.insert_cleaned_listings(
                cleaned_listings, run_id
            )
            logger.info(
                "Cleaned listings persisted",
                extra={"run_id": run_id, "inserted": inserted}
            )

        # Persist compliance_flags to database
        compliance_flags_raw = final_values.get("compliance_flags", [])
        flag_dicts = []
        for flag in compliance_flags_raw:
            if hasattr(flag, 'model_dump'):
                flag_dicts.append(flag.model_dump())
            elif isinstance(flag, dict):
                flag_dicts.append(flag)

        if flag_dicts:
            inserted_flags = await repo.insert_compliance_flags(
                flag_dicts, run_id
            )
            logger.info(
                "Compliance flags persisted",
                extra={"run_id": run_id, "inserted": inserted_flags}
            )

        # Insert price history
        for item in cleaned_listings_raw:
            try:
                if hasattr(item, 'price_per_sqm'):
                    price_sqm = item.price_per_sqm
                    lid = item.listing_id
                    dist = item.district or ""
                    psar = item.price_sar or 0.0
                else:
                    price_sqm = item.get('price_per_sqm')
                    lid = item.get('listing_id', '')
                    dist = item.get('district') or ""
                    psar = item.get('price_sar') or 0.0

                if price_sqm:
                    from datetime import datetime, timezone
                    await repo.insert_price_history(
                        listing_id=lid,
                        district=dist,
                        price_sar=float(psar),
                        price_per_sqm=float(price_sqm),
                        recorded_at=datetime.now(
                            timezone.utc
                        ).isoformat(),
                    )
            except Exception as ph_err:
                logger.warning(
                    "Price history insert failed",
                    extra={"error": str(ph_err)}
                )

        # Update analysis run as completed
        await repo.update_analysis_run(
            run_id=run_id,
            status="completed",
            summary=str(
                final_values.get("investment_report", "")
            )[:500],
            total_listings=len(cleaned_listings),
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
