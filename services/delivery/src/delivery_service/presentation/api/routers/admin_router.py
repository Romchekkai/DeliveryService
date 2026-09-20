from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from delivery_service.infrastructure.scheduler import (
    CALCULATE_COSTS_JOB_ID,
    run_calculate_delivery_costs,
    scheduler,
)
from delivery_service.infrastructure.security.jwt_verifier import TokenPayload
from delivery_service.presentation.api.dependencies import require_admin
from delivery_service.presentation.api.schemas.parcel_schemas import TaskRunResponse

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/admin/tasks", tags=["admin"])


@router.post(
    "/calculate-costs",
    response_model=TaskRunResponse,
    summary="Start calculate costs",
)
async def run_calculate_costs(
    current_user: TokenPayload = Depends(require_admin),
) -> TaskRunResponse:
    logger.info("manual_task_triggered", task=CALCULATE_COSTS_JOB_ID, by=str(current_user.user_id))
    try:
        processed = await run_calculate_delivery_costs(trigger="manual")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)) from e

    return TaskRunResponse(
        task=CALCULATE_COSTS_JOB_ID,
        processed=processed,
        detail=f"Managed tasks: {processed}",
    )


@router.get("", summary="List of recurring tasks")
async def list_jobs(
    current_user: TokenPayload = Depends(require_admin),
) -> dict[str, Any]:
    return {
        "running": scheduler.running,
        "jobs": [
            {
                "id": job.id,
                "next_run_time": str(job.next_run_time) if job.next_run_time else None,
                "trigger": str(job.trigger),
            }
            for job in scheduler.get_jobs()
        ],
    }
