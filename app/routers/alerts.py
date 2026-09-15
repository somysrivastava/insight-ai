from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.models.alert_history import AlertHistory
from app.models.alert_rule import AlertRule
from app.models.workspace_member import WorkspaceMember
from app.schemas.alert import (
    AlertHistoryResponse,
    AlertRuleCreateRequest,
    AlertRuleResponse,
    AlertRuleUpdateRequest,
)
from app.schemas.jobs import JobSubmitResponse
from app.services.access_control import require_dataset_access, require_workspace_membership
from app.services.auth_service import get_current_user
from app.services.job_service import record_job_owner
from app.services.storage_service import load_dataframe
from app.tasks.alert_tasks import run_single_alert_check_task

router = APIRouter(prefix="/alerts", tags=["Alerts"])


def _get_owned_rule(db: Session, alert_rule_id: int, user_id: int) -> AlertRule:
    rule = db.query(AlertRule).filter(AlertRule.id == alert_rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    require_workspace_membership(db, rule.workspace_id, user_id)
    return rule


def _load_columns(dataset) -> list[str]:
    return list(load_dataframe(dataset.file_path).columns)


@router.post("", response_model=AlertRuleResponse, status_code=201)
def create_alert_rule(
    request: AlertRuleCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset = require_dataset_access(db, request.dataset_id, current_user.id)
    if request.column not in _load_columns(dataset):
        raise HTTPException(status_code=400, detail=f"Column '{request.column}' not found in dataset.")

    rule = AlertRule(
        workspace_id=dataset.workspace_id,
        created_by=current_user.id,
        name=request.name,
        dataset_id=request.dataset_id,
        column=request.column,
        metric=request.metric,
        condition=request.condition,
        threshold=request.threshold,
        use_statistical=request.use_statistical,
        z_score_threshold=request.z_score_threshold,
        frequency=request.frequency,
        recipients=[str(r) for r in request.recipients],
        is_active=True,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.get("", response_model=list[AlertRuleResponse])
def list_alert_rules(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Lists alert rules across every workspace the current user belongs to."""
    return (
        db.query(AlertRule)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == AlertRule.workspace_id)
        .filter(WorkspaceMember.user_id == current_user.id)
        .all()
    )


@router.get("/{alert_rule_id}", response_model=AlertRuleResponse)
def get_alert_rule(alert_rule_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _get_owned_rule(db, alert_rule_id, current_user.id)


@router.patch("/{alert_rule_id}", response_model=AlertRuleResponse)
def update_alert_rule(
    alert_rule_id: int,
    request: AlertRuleUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rule = _get_owned_rule(db, alert_rule_id, current_user.id)
    updates = request.model_dump(exclude_unset=True)

    if "column" in updates and updates["column"] not in _load_columns(rule.dataset):
        raise HTTPException(status_code=400, detail=f"Column '{updates['column']}' not found in dataset.")

    for field, value in updates.items():
        if field == "recipients":
            value = [str(r) for r in value]
        setattr(rule, field, value)

    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/{alert_rule_id}", status_code=204, response_class=Response)
def delete_alert_rule(alert_rule_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    rule = _get_owned_rule(db, alert_rule_id, current_user.id)
    db.delete(rule)
    db.commit()
    return Response(status_code=204)


@router.get("/{alert_rule_id}/history", response_model=list[AlertHistoryResponse])
def get_alert_history(alert_rule_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _get_owned_rule(db, alert_rule_id, current_user.id)
    return (
        db.query(AlertHistory)
        .filter(AlertHistory.alert_rule_id == alert_rule_id)
        .order_by(AlertHistory.checked_at.desc())
        .all()
    )


@router.post("/{alert_rule_id}/check", response_model=JobSubmitResponse, status_code=202)
def check_alert_rule_now(alert_rule_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Manual test trigger — runs the real check and sends a real email if it fires."""
    _get_owned_rule(db, alert_rule_id, current_user.id)

    task = run_single_alert_check_task.delay(alert_rule_id)
    record_job_owner(task.id, current_user.id)
    return JobSubmitResponse(task_id=task.id)
