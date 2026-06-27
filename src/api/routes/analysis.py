"""Analysis pipeline API endpoints."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, status

from src.api.schemas import AnalysisRequest, AnalysisResponse, RunStatusResponse
from src.core.logging_setup import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/analyze", tags=["analysis"])


@router.post(
    "",
    response_model=AnalysisResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_analysis(request: AnalysisRequest) -> AnalysisResponse:
    """Submit a new real estate analysis pipeline run.

    Queues the LangGraph pipeline as a Celery background task.
    Returns immediately with a run_id for status polling.

    Args:
        request: Analysis configuration with districts and options.

    Returns:
        AnalysisResponse with run_id and status polling URL.

    Raises:
        HTTPException 500: If task queuing fails.
    """
    from src.workers.tasks import run_analysis_pipeline

    run_id = str(uuid.uuid4())

    try:
        run_analysis_pipeline.apply_async(
            kwargs={
                "run_id": run_id,
                "districts": request.districts,
                "max_listings_per_district": request.max_listings_per_district,
                "use_mock_data": request.use_mock_data,
            },
            task_id=run_id,
        )

        logger.info(
            "Analysis task queued",
            extra={"run_id": run_id, "districts": request.districts},
        )

        return AnalysisResponse(
            run_id=run_id,
            status="queued",
            status_url=f"/analyze/{run_id}",
        )

    except Exception as exc:
        logger.error("Failed to queue analysis task", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue analysis: {exc}",
        ) from exc


@router.get(
    "/{run_id}",
    response_model=RunStatusResponse,
)
async def get_analysis_status(run_id: str) -> RunStatusResponse:
    """Poll analysis pipeline status and retrieve results.

    Checks Celery task state for live status. When the task has
    completed, the task result already contains the full pipeline
    output (status, phase, and investment report).

    Args:
        run_id: Pipeline run identifier from submit_analysis.

    Returns:
        RunStatusResponse with current status and report when complete.
    """
    from src.workers.celery_app import celery_app

    task_result = celery_app.AsyncResult(run_id)
    celery_state = task_result.state

    status_map = {
        "PENDING": "queued",
        "STARTED": "running",
        "SUCCESS": "complete",
        "FAILURE": "failed",
        "RETRY": "running",
    }
    our_status = status_map.get(celery_state, "running")

    if our_status == "complete" and task_result.result:
        result_data: dict[str, Any] = task_result.result
        return RunStatusResponse(
            run_id=run_id,
            status="complete",
            current_phase=result_data.get("current_phase", "complete"),
            created_at=result_data.get("created_at", ""),
            completed_at=result_data.get("completed_at", ""),
            investment_report=result_data.get("investment_report"),
            error=None,
        )

    if our_status == "failed":
        error_info = str(task_result.result) if task_result.result else "Unknown error"
        return RunStatusResponse(
            run_id=run_id,
            status="failed",
            current_phase="failed",
            created_at="",
            error=error_info,
        )

    return RunStatusResponse(
        run_id=run_id,
        status=our_status,  # type: ignore[arg-type]
        current_phase=celery_state.lower(),
        created_at="",
    )
