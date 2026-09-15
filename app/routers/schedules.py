from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.models.saved_join import SavedJoin
from app.models.scheduled_report import ScheduledReport
from app.models.workspace_member import WorkspaceMember
from app.schemas.jobs import JobSubmitResponse
from app.schemas.schedule import (
    ScheduledReportCreateRequest,
    ScheduledReportResponse,
    ScheduledReportUpdateRequest,
)
from app.services.access_control import require_dataset_access, require_workspace_membership
from app.services.auth_service import get_current_user
from app.services.job_service import record_job_owner
from app.services.schedule_service import compute_next_run_at
from app.tasks.scheduled_tasks import run_scheduled_report_task

router = APIRouter(prefix="/schedules", tags=["Scheduled Reports"])


def _resolve_workspace_id(db: Session, user_id: int, source_type: str, source_id: int) -> int:
    """Validates the source exists and the user has access, returning its workspace_id."""
    if source_type in ("dataset_query", "report"):
        dataset = require_dataset_access(db, source_id, user_id)
        return dataset.workspace_id

    if source_type == "join_query":
        saved_join = db.query(SavedJoin).filter(SavedJoin.id == source_id).first()
        if not saved_join:
            raise HTTPException(status_code=404, detail="Saved join not found")
        require_workspace_membership(db, saved_join.workspace_id, user_id)
        return saved_join.workspace_id

    raise HTTPException(status_code=400, detail=f"Unsupported source_type: {source_type}")


def _get_owned_schedule(db: Session, schedule_id: int, user_id: int) -> ScheduledReport:
    schedule = db.query(ScheduledReport).filter(ScheduledReport.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Scheduled report not found")
    require_workspace_membership(db, schedule.workspace_id, user_id)
    return schedule


@router.post("", response_model=ScheduledReportResponse, status_code=201)
def create_schedule(
    request: ScheduledReportCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    workspace_id = _resolve_workspace_id(db, current_user.id, request.source_type, request.source_id)

    next_run_at = compute_next_run_at(
        request.frequency, request.hour, request.day_of_week, request.day_of_month, after=datetime.now(timezone.utc)
    )

    schedule = ScheduledReport(
        workspace_id=workspace_id,
        created_by=current_user.id,
        name=request.name,
        source_type=request.source_type,
        source_id=request.source_id,
        question=request.question,
        export_format=request.export_format,
        frequency=request.frequency,
        day_of_week=request.day_of_week,
        day_of_month=request.day_of_month,
        hour=request.hour,
        recipients=[str(r) for r in request.recipients],
        is_active=True,
        next_run_at=next_run_at,
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return schedule


@router.get("", response_model=list[ScheduledReportResponse])
def list_schedules(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Lists scheduled reports across every workspace the current user belongs to."""
    return (
        db.query(ScheduledReport)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == ScheduledReport.workspace_id)
        .filter(WorkspaceMember.user_id == current_user.id)
        .all()
    )


@router.get("/{schedule_id}", response_model=ScheduledReportResponse)
def get_schedule(schedule_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _get_owned_schedule(db, schedule_id, current_user.id)


@router.patch("/{schedule_id}", response_model=ScheduledReportResponse)
def update_schedule(
    schedule_id: int,
    request: ScheduledReportUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    schedule = _get_owned_schedule(db, schedule_id, current_user.id)
    updates = request.model_dump(exclude_unset=True)

    schedule_fields_changed = any(f in updates for f in ("frequency", "day_of_week", "day_of_month", "hour"))
    reactivated = updates.get("is_active") is True and not schedule.is_active

    for field, value in updates.items():
        if field == "recipients":
            value = [str(r) for r in value]
        setattr(schedule, field, value)

    if schedule_fields_changed or reactivated:
        # A PATCH is partial, so frequency can change without the caller
        # re-specifying day_of_week/day_of_month — validate the *merged*
        # state (not just what's in this request), since compute_next_run_at
        # would otherwise crash on a weekly/monthly schedule with no day set.
        if schedule.frequency == "weekly" and schedule.day_of_week is None:
            raise HTTPException(status_code=422, detail="'day_of_week' is required when frequency is 'weekly'.")
        if schedule.frequency == "monthly" and schedule.day_of_month is None:
            raise HTTPException(status_code=422, detail="'day_of_month' is required when frequency is 'monthly'.")
        if schedule.frequency == "daily":
            schedule.day_of_week = None
            schedule.day_of_month = None
        elif schedule.frequency == "weekly":
            schedule.day_of_month = None
        elif schedule.frequency == "monthly":
            schedule.day_of_week = None

        schedule.next_run_at = compute_next_run_at(
            schedule.frequency, schedule.hour, schedule.day_of_week, schedule.day_of_month,
            after=datetime.now(timezone.utc),
        )

    db.commit()
    db.refresh(schedule)
    return schedule


@router.delete("/{schedule_id}", status_code=204, response_class=Response)
def delete_schedule(schedule_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    schedule = _get_owned_schedule(db, schedule_id, current_user.id)
    db.delete(schedule)
    db.commit()
    return Response(status_code=204)


@router.post("/{schedule_id}/run", response_model=JobSubmitResponse, status_code=202)
def run_schedule_now(schedule_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Triggers a schedule immediately, for testing. Runs the real export
    and sends the real email, but does not touch last_run_at/next_run_at
    — a manual test shouldn't shift when the schedule actually fires next.
    """
    _get_owned_schedule(db, schedule_id, current_user.id)

    task = run_scheduled_report_task.delay(schedule_id, True)
    record_job_owner(task.id, current_user.id)
    return JobSubmitResponse(task_id=task.id)
