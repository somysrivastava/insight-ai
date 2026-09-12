from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException

from app.models import User
from app.schemas.jobs import JobResponse
from app.services.auth_service import get_current_user
from app.services.job_service import get_job_owner
from app.worker import celery_app

router = APIRouter(prefix="/jobs", tags=["Jobs"])

_CELERY_STATUS_MAP = {
    "PENDING": "pending",
    "STARTED": "started",
    "RETRY": "started",
    "SUCCESS": "success",
    "FAILURE": "failed",
    "REVOKED": "failed",
}


@router.get("/{task_id}", response_model=JobResponse)
def get_job(task_id: str, current_user: User = Depends(get_current_user)):
    owner_id = get_job_owner(task_id)
    if owner_id is None:
        raise HTTPException(status_code=404, detail="Job not found or has expired.")
    if owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    async_result = AsyncResult(task_id, app=celery_app)
    status = _CELERY_STATUS_MAP.get(async_result.state, "pending")

    result = async_result.result if status == "success" else None
    error = str(async_result.result) if status == "failed" and async_result.result else None

    return JobResponse(task_id=task_id, status=status, result=result, error=error)
