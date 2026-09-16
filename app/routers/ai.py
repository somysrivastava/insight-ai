from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.rate_limiter import limiter
from app.schemas.ai import QueryRequest, QueryResponse
from app.schemas.jobs import JobSubmitResponse
from app.services import ai_service
from app.services.access_control import require_dataset_access
from app.services.auth_service import get_current_user
from app.services.job_service import record_job_owner
from app.tasks.ai_tasks import run_query_task

router = APIRouter(prefix="/datasets", tags=["AI Queries"])


@router.post("/{dataset_id}/query", response_model=QueryResponse)
@limiter.limit("10/hour")
def query_dataset(
    request: Request,
    response: Response,
    dataset_id: int,
    body: QueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset = require_dataset_access(db, dataset_id, current_user.id)

    try:
        result = ai_service.get_cached_answer(dataset, body.question, db)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Dataset file not found in storage")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")

    return result


@router.post("/{dataset_id}/query/async", response_model=JobSubmitResponse, status_code=202)
@limiter.limit("10/hour")
def query_dataset_async(
    request: Request,
    response: Response,
    dataset_id: int,
    body: QueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Same as POST /{dataset_id}/query, but returns immediately with a
    task_id instead of blocking on the OpenAI call. Poll the result via
    GET /jobs/{task_id}. The synchronous endpoint above is untouched —
    this is additive, not a replacement.
    """
    require_dataset_access(db, dataset_id, current_user.id)

    task = run_query_task.delay(dataset_id, current_user.id, body.question)
    record_job_owner(task.id, current_user.id)
    return JobSubmitResponse(task_id=task.id)
