from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.rate_limiter import limiter
from app.schemas.jobs import JobSubmitResponse
from app.services.access_control import require_dataset_access
from app.services.auth_service import get_current_user
from app.services.analytics_service import get_cached_breakdown, get_cached_insights, get_cached_trends
from app.services.job_service import record_job_owner
from app.tasks.analytics_tasks import (
    generate_breakdown_task,
    generate_insights_task,
    generate_trends_task,
)

router = APIRouter(
    prefix = "/datasets",
    tags=["analytics"]
)

@router.get("/{dataset_id}/analytics")
@limiter.limit("100/hour")
def get_insights(request: Request, response: Response, dataset_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    dataset = require_dataset_access(db, dataset_id, current_user.id)
    try:
        result = get_cached_insights(dataset_id, str(dataset.file_path))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"error Generating insight: {str(e)}")
    return {
        "dataset_id": dataset_id,
        "dataset_name": dataset.filename,
        **result
    }

@router.get("/{dataset_id}/trends/")
@limiter.limit("100/hour")
def get_trends(request: Request, response: Response, dataset_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    dataset = require_dataset_access(db, dataset_id, current_user.id)
    try:
        result = get_cached_trends(dataset_id, str(dataset.file_path))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"error Generating trends: {str(e)}")
    return {
        "dataset_id": dataset_id,
        "dataset_name": dataset.filename,
        **result
    }


@router.get("/{dataset_id}/breakdown")
@limiter.limit("100/hour")
def get_breakdown(request: Request, response: Response, dataset_id: int, group_by: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    dataset = require_dataset_access(db, dataset_id, current_user.id)
    try:
        result = get_cached_breakdown(dataset_id, str(dataset.file_path), group_by)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"error Generating breakdown: {str(e)}")
    return {
        "dataset_id": dataset_id,
        "dataset_name": dataset.filename,
        **result
    }


@router.post("/{dataset_id}/analytics/async", response_model=JobSubmitResponse, status_code=202)
@limiter.limit("100/hour")
def get_insights_async(request: Request, response: Response, dataset_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Same as GET /{dataset_id}/analytics, but returns a task_id immediately. Poll via GET /jobs/{task_id}."""
    require_dataset_access(db, dataset_id, current_user.id)
    task = generate_insights_task.delay(dataset_id, current_user.id)
    record_job_owner(task.id, current_user.id)
    return JobSubmitResponse(task_id=task.id)


@router.post("/{dataset_id}/trends/async", response_model=JobSubmitResponse, status_code=202)
@limiter.limit("100/hour")
def get_trends_async(request: Request, response: Response, dataset_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Same as GET /{dataset_id}/trends/, but returns a task_id immediately. Poll via GET /jobs/{task_id}."""
    require_dataset_access(db, dataset_id, current_user.id)
    task = generate_trends_task.delay(dataset_id, current_user.id)
    record_job_owner(task.id, current_user.id)
    return JobSubmitResponse(task_id=task.id)


@router.post("/{dataset_id}/breakdown/async", response_model=JobSubmitResponse, status_code=202)
@limiter.limit("100/hour")
def get_breakdown_async(request: Request, response: Response, dataset_id: int, group_by: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Same as GET /{dataset_id}/breakdown, but returns a task_id immediately. Poll via GET /jobs/{task_id}."""
    require_dataset_access(db, dataset_id, current_user.id)
    task = generate_breakdown_task.delay(dataset_id, current_user.id, group_by)
    record_job_owner(task.id, current_user.id)
    return JobSubmitResponse(task_id=task.id)
