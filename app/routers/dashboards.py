from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.models.dashboard import Dashboard
from app.models.dashboard_pin import DashboardPin
from app.schemas.dashboard import (
    DashboardCreateRequest,
    DashboardDetailResponse,
    DashboardPinCreateRequest,
    DashboardPinResponse,
    DashboardPinUpdateRequest,
    DashboardResponse,
    DashboardUpdateRequest,
)
from app.schemas.jobs import JobSubmitResponse
from app.services import dashboard_service
from app.services.access_control import require_workspace_access, require_workspace_membership
from app.services.auth_service import get_current_user
from app.services.job_service import record_job_owner
from app.tasks.dashboard_tasks import refresh_dashboard_task, refresh_single_pin_task

router = APIRouter(prefix="/dashboards", tags=["Dashboards"])


def _get_owned_dashboard(db: Session, dashboard_id: int, user_id: int) -> Dashboard:
    dashboard = db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    require_workspace_membership(db, dashboard.workspace_id, user_id)
    return dashboard


def _get_owned_pin(db: Session, dashboard_id: int, pin_id: int, user_id: int) -> DashboardPin:
    dashboard = _get_owned_dashboard(db, dashboard_id, user_id)
    pin = (
        db.query(DashboardPin)
        .filter(DashboardPin.id == pin_id, DashboardPin.dashboard_id == dashboard.id)
        .first()
    )
    if not pin:
        raise HTTPException(status_code=404, detail="Dashboard pin not found")
    return pin


@router.post("", response_model=DashboardResponse, status_code=201)
def create_dashboard(
    request: DashboardCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    workspace_id = require_workspace_access(db, current_user.id, request.workspace_id)
    return dashboard_service.create_dashboard(
        db, workspace_id, current_user.id, request.name, request.description, request.is_default
    )


@router.get("", response_model=list[DashboardResponse])
def list_dashboards(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Lists dashboards across every workspace the current user belongs to."""
    return dashboard_service.list_dashboards(db, current_user.id)


@router.get("/{dashboard_id}", response_model=DashboardDetailResponse)
def get_dashboard(dashboard_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Returns the dashboard with every pin's last cached_result — never re-executes anything. Use .../refresh for that."""
    return _get_owned_dashboard(db, dashboard_id, current_user.id)


@router.patch("/{dashboard_id}", response_model=DashboardResponse)
def update_dashboard(
    dashboard_id: int,
    request: DashboardUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dashboard = _get_owned_dashboard(db, dashboard_id, current_user.id)
    for field, value in request.model_dump(exclude_unset=True).items():
        setattr(dashboard, field, value)
    db.commit()
    db.refresh(dashboard)
    return dashboard


@router.delete("/{dashboard_id}", status_code=204, response_class=Response)
def delete_dashboard(
    dashboard_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    dashboard = _get_owned_dashboard(db, dashboard_id, current_user.id)
    db.delete(dashboard)
    db.commit()
    return Response(status_code=204)


@router.post("/{dashboard_id}/pins", response_model=DashboardPinResponse, status_code=201)
def add_pin(
    dashboard_id: int,
    request: DashboardPinCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Runs the pin's query immediately — a pin that can't run isn't saved. See app/services/dashboard_service.py."""
    dashboard = _get_owned_dashboard(db, dashboard_id, current_user.id)
    try:
        return dashboard_service.add_pin(
            db, dashboard, current_user.id, request.title, request.pin_type, request.source_id, request.query_params
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Source dataset file not found in storage")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not run this pin's query: {str(e)}")


@router.delete("/{dashboard_id}/pins/{pin_id}", status_code=204, response_class=Response)
def remove_pin(
    dashboard_id: int, pin_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    pin = _get_owned_pin(db, dashboard_id, pin_id, current_user.id)
    dashboard_service.remove_pin(db, pin)
    return Response(status_code=204)


@router.patch("/{dashboard_id}/pins/{pin_id}", response_model=DashboardPinResponse)
def update_pin(
    dashboard_id: int,
    pin_id: int,
    request: DashboardPinUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pin = _get_owned_pin(db, dashboard_id, pin_id, current_user.id)
    for field, value in request.model_dump(exclude_unset=True).items():
        setattr(pin, field, value)
    db.commit()
    db.refresh(pin)
    return pin


@router.post("/{dashboard_id}/refresh", response_model=JobSubmitResponse, status_code=202)
def refresh_dashboard(
    dashboard_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Async refresh of every pin on this dashboard. Poll GET /jobs/{task_id}, then re-fetch GET /dashboards/{id}."""
    _get_owned_dashboard(db, dashboard_id, current_user.id)
    task = refresh_dashboard_task.delay(dashboard_id)
    record_job_owner(task.id, current_user.id)
    return JobSubmitResponse(task_id=task.id)


@router.post("/{dashboard_id}/pins/{pin_id}/refresh", response_model=JobSubmitResponse, status_code=202)
def refresh_pin(
    dashboard_id: int, pin_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    _get_owned_pin(db, dashboard_id, pin_id, current_user.id)
    task = refresh_single_pin_task.delay(pin_id)
    record_job_owner(task.id, current_user.id)
    return JobSubmitResponse(task_id=task.id)
