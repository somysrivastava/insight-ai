from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.models.saved_join import SavedJoin
from app.schemas.jobs import JobSubmitResponse
from app.schemas.join import (
    JoinQueryRequest,
    JoinQueryResponse,
    SavedJoinQueryRequest,
    SavedJoinResponse,
)
from app.services import ai_service, join_service
from app.services.access_control import require_dataset_access, require_workspace_membership
from app.services.auth_service import get_current_user
from app.services.job_service import record_job_owner
from app.tasks.join_tasks import run_join_query_task, run_saved_join_query_task

router = APIRouter(prefix="/joins", tags=["Joins"])


def _handle_join_errors(fn, *args, **kwargs):
    """
    Every join operation can fail for the same set of reasons (bad join
    spec, missing dataset, access denied, unreadable file) regardless of
    which endpoint triggered it — one place to map them to HTTP status
    codes instead of repeating the same except block five times.
    """
    try:
        return fn(*args, **kwargs)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Dataset file not found in storage")
    except ValueError as e:
        # Covers both "dataset not found" and join-spec validation errors
        # (unknown/duplicate alias, disconnected dataset, bad column,
        # mixed workspaces). Referenced by id inside the request body,
        # not the URL, so 400 (invalid request) fits better than 404
        # here — see app/services/join_service.py for what raises this.
        raise HTTPException(status_code=400, detail=str(e))


def _save_if_named(db: Session, workspace_id: int, user_id: int, request: JoinQueryRequest) -> int | None:
    if not request.name:
        return None
    existing = (
        db.query(SavedJoin)
        .filter(SavedJoin.workspace_id == workspace_id, SavedJoin.name == request.name)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409, detail=f"A saved join named '{request.name}' already exists in this workspace."
        )
    saved = SavedJoin(
        workspace_id=workspace_id,
        user_id=user_id,
        name=request.name,
        datasets=[d.model_dump() for d in request.datasets],
        joins=[j.model_dump() for j in request.joins],
    )
    db.add(saved)
    db.commit()
    db.refresh(saved)
    return saved.id


@router.post("", response_model=JoinQueryResponse)
def create_and_query_join(
    request: JoinQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Executes an inline multi-dataset join and answers a question against
    the result. If `name` is given, the join definition is also saved
    for reuse via POST /joins/{id}/query — saved only after the join
    itself is confirmed valid and executable.
    """
    dataframes, workspace_id = _handle_join_errors(
        join_service.load_and_validate_datasets, db, current_user.id, request.datasets
    )
    joined_df = _handle_join_errors(join_service.execute_join, dataframes, request.joins)

    join_id = _save_if_named(db, workspace_id, current_user.id, request)

    result = _handle_join_errors(ai_service.answer_query_for_df, joined_df, request.question)
    return JoinQueryResponse(**result, join_id=join_id)


@router.post("/async", response_model=JobSubmitResponse, status_code=202)
def create_and_query_join_async(
    request: JoinQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Same as POST /joins, but returns immediately with a task_id. The
    submission-time check here only confirms each dataset exists and is
    accessible (no file reads, no join execution, no AI call) — the
    actual join + save + answer all happen in the task, which
    re-validates access independently regardless (app/tasks/join_tasks.py).
    """
    workspace_id = None
    for ref in request.datasets:
        dataset = require_dataset_access(db, ref.id, current_user.id)
        if workspace_id is None:
            workspace_id = dataset.workspace_id
        elif dataset.workspace_id != workspace_id:
            raise HTTPException(
                status_code=400,
                detail="All datasets in a join must belong to the same workspace.",
            )

    if request.name:
        existing = (
            db.query(SavedJoin)
            .filter(SavedJoin.workspace_id == workspace_id, SavedJoin.name == request.name)
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=409, detail=f"A saved join named '{request.name}' already exists in this workspace."
            )

    task = run_join_query_task.delay(
        [d.model_dump() for d in request.datasets],
        [j.model_dump() for j in request.joins],
        request.question,
        current_user.id,
        request.name,
    )
    record_job_owner(task.id, current_user.id)
    return JobSubmitResponse(task_id=task.id)


@router.get("", response_model=list[SavedJoinResponse])
def list_saved_joins(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Lists saved joins across every workspace the current user belongs to."""
    from app.models.workspace_member import WorkspaceMember

    rows = (
        db.query(SavedJoin)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == SavedJoin.workspace_id)
        .filter(WorkspaceMember.user_id == current_user.id)
        .all()
    )
    return rows


@router.get("/{join_id}", response_model=SavedJoinResponse)
def get_saved_join(join_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    saved = db.query(SavedJoin).filter(SavedJoin.id == join_id).first()
    if not saved:
        raise HTTPException(status_code=404, detail="Saved join not found")
    require_workspace_membership(db, saved.workspace_id, current_user.id)
    return saved


@router.delete("/{join_id}", status_code=204, response_class=Response)
def delete_saved_join(join_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    saved = db.query(SavedJoin).filter(SavedJoin.id == join_id).first()
    if not saved:
        raise HTTPException(status_code=404, detail="Saved join not found")
    require_workspace_membership(db, saved.workspace_id, current_user.id)
    db.delete(saved)
    db.commit()
    return Response(status_code=204)


@router.post("/{join_id}/query", response_model=JoinQueryResponse)
def query_saved_join(
    join_id: int,
    request: SavedJoinQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    saved = db.query(SavedJoin).filter(SavedJoin.id == join_id).first()
    if not saved:
        raise HTTPException(status_code=404, detail="Saved join not found")
    require_workspace_membership(db, saved.workspace_id, current_user.id)

    dataframes, _ = _handle_join_errors(
        join_service.load_and_validate_datasets, db, current_user.id, saved.datasets
    )
    joined_df = _handle_join_errors(join_service.execute_join, dataframes, saved.joins)
    result = _handle_join_errors(ai_service.answer_query_for_df, joined_df, request.question)
    return JoinQueryResponse(**result, join_id=saved.id)


@router.post("/{join_id}/query/async", response_model=JobSubmitResponse, status_code=202)
def query_saved_join_async(
    join_id: int,
    request: SavedJoinQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    saved = db.query(SavedJoin).filter(SavedJoin.id == join_id).first()
    if not saved:
        raise HTTPException(status_code=404, detail="Saved join not found")
    require_workspace_membership(db, saved.workspace_id, current_user.id)

    task = run_saved_join_query_task.delay(join_id, request.question, current_user.id)
    record_job_owner(task.id, current_user.id)
    return JobSubmitResponse(task_id=task.id)
