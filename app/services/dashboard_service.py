# WHY THIS FILE EXISTS:
# Owns everything about a Dashboard's pins: turning a pin's
# (pin_type, source_id, query_params) into a real result by dispatching
# to whichever existing service already knows how to answer it
# (ai_service for dataset_query/join_query, analytics_service for
# analytics, kpi_service/report_service for report) — this file adds no
# new query logic of its own, it only wires pins to what already exists.
#
# Framework-agnostic on purpose, same as access_control.py: raises plain
# ValueError/PermissionError, not HTTPException, so both the router and
# the Celery tasks (app/tasks/dashboard_tasks.py) can call it directly.

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.dashboard import Dashboard
from app.models.dashboard_pin import DashboardPin
from app.models.saved_join import SavedJoin
from app.models.workspace_member import WorkspaceMember
from app.services import ai_service, join_service
from app.services.access_control import check_workspace_membership, get_dataset_for_user
from app.services.analytics_service import get_cached_breakdown, get_cached_insights, get_cached_trends
from app.services.report_service import get_cached_executive_summary, get_cached_full_report, get_cached_kpis
from app.services.storage_service import load_dataframe

PIN_TYPES = ("dataset_query", "join_query", "analytics", "report")


def create_dashboard(
    db: Session,
    workspace_id: int,
    created_by: int,
    name: str,
    description: Optional[str],
    is_default: bool,
) -> Dashboard:
    dashboard = Dashboard(
        workspace_id=workspace_id,
        created_by=created_by,
        name=name,
        description=description,
        is_default=is_default,
    )
    db.add(dashboard)
    db.commit()
    db.refresh(dashboard)
    return dashboard


def list_dashboards(db: Session, user_id: int) -> list[Dashboard]:
    """Lists dashboards across every workspace the current user belongs to, same pattern as SavedJoin/AlertRule."""
    return (
        db.query(Dashboard)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Dashboard.workspace_id)
        .filter(WorkspaceMember.user_id == user_id)
        .all()
    )


def find_dashboards_pinning_dataset(db: Session, dataset_id: int) -> list[int]:
    """
    Distinct dashboard_ids with a pin directly sourced from this dataset
    (Day 23 — called after a version push/rollback to know which
    dashboards to refresh). Only dataset_query/analytics/report pins
    are included, since source_id for those three is a dataset id
    directly. join_query pins aren't: source_id there is a SavedJoin
    id, and resolving "does this join touch this dataset" needs
    inspecting SavedJoin.datasets JSONB — a real follow-up, not in
    scope here (same deliberate limit as Day 22's dictionary
    enrichment not reaching join queries).
    """
    rows = (
        db.query(DashboardPin.dashboard_id)
        .filter(
            DashboardPin.pin_type.in_(("dataset_query", "analytics", "report")),
            DashboardPin.source_id == dataset_id,
        )
        .distinct()
        .all()
    )
    return [r[0] for r in rows]


def _execute_pin(
    db: Session,
    pin_type: str,
    source_id: int,
    query_params: dict,
    pinned_by: int,
    expected_workspace_id: int,
) -> dict[str, Any]:
    """
    Re-runs whatever a pin describes and returns the raw result — the
    single dispatch point used both when a pin is first created (fails
    loudly if the query can't run — see add_pin) and on every later
    refresh (fails softly — see refresh_pin). Independently re-validates
    access every time, the same "a task may run well after submission,
    by a worker with no HTTP context" reasoning as every other Celery
    task in this app (app/tasks/common.py), and confirms the resolved
    source actually belongs to the dashboard's own workspace — a pin
    can't reach across workspaces even if the acting user happens to
    belong to more than one.
    """
    params = query_params or {}

    if pin_type == "dataset_query":
        dataset = get_dataset_for_user(db, source_id, pinned_by)
        if dataset.workspace_id != expected_workspace_id:
            raise ValueError("Pinned dataset does not belong to this dashboard's workspace.")
        question = params.get("question")
        if not question:
            raise ValueError("A 'dataset_query' pin requires 'question' in query_params.")
        return ai_service.get_cached_answer(dataset, question, db)

    if pin_type == "join_query":
        saved = db.query(SavedJoin).filter(SavedJoin.id == source_id).first()
        if not saved:
            raise ValueError(f"Saved join {source_id} not found.")
        check_workspace_membership(db, saved.workspace_id, pinned_by)
        if saved.workspace_id != expected_workspace_id:
            raise ValueError("Pinned join does not belong to this dashboard's workspace.")
        question = params.get("question")
        if not question:
            raise ValueError("A 'join_query' pin requires 'question' in query_params.")
        dataframes, _ = join_service.load_and_validate_datasets(db, pinned_by, saved.datasets)
        joined_df = join_service.execute_join(dataframes, saved.joins)
        return ai_service.answer_query_for_df(joined_df, question)

    if pin_type == "analytics":
        dataset = get_dataset_for_user(db, source_id, pinned_by)
        if dataset.workspace_id != expected_workspace_id:
            raise ValueError("Pinned dataset does not belong to this dashboard's workspace.")
        operation = params.get("operation")
        if operation == "insights":
            return get_cached_insights(source_id, str(dataset.file_path))
        if operation == "trends":
            return get_cached_trends(source_id, str(dataset.file_path))
        if operation == "breakdown":
            group_by = params.get("group_by")
            if not group_by:
                raise ValueError("An 'analytics' pin with operation 'breakdown' requires 'group_by' in query_params.")
            return get_cached_breakdown(source_id, str(dataset.file_path), group_by)
        raise ValueError(
            f"Unsupported analytics operation '{operation}' — must be 'insights', 'trends', or 'breakdown'."
        )

    if pin_type == "report":
        dataset = get_dataset_for_user(db, source_id, pinned_by)
        if dataset.workspace_id != expected_workspace_id:
            raise ValueError("Pinned dataset does not belong to this dashboard's workspace.")
        report_type = params.get("report_type")
        df = load_dataframe(dataset.file_path)
        if report_type == "kpis":
            return get_cached_kpis(dataset.id, df)
        if report_type == "summary":
            kpis = get_cached_kpis(dataset.id, df)
            return get_cached_executive_summary(dataset.id, dataset.filename, kpis).model_dump()
        if report_type == "full":
            return get_cached_full_report(dataset.id, dataset.filename, df).model_dump()
        raise ValueError(f"Unsupported report_type '{report_type}' — must be 'kpis', 'summary', or 'full'.")

    raise ValueError(f"Unsupported pin_type '{pin_type}' — must be one of {PIN_TYPES}.")


def add_pin(
    db: Session,
    dashboard: Dashboard,
    pinned_by: int,
    title: str,
    pin_type: str,
    source_id: int,
    query_params: dict,
) -> DashboardPin:
    """
    Executes the pin's query once before saving anything — a pin that
    can't actually run (bad column, missing dataset, disconnected join)
    is never persisted, matching the "save only if valid and executable"
    precedent set by SavedJoin (Day 17) and AlertRule's column-existence
    check (Day 20). Any exception here propagates to the caller
    unhandled; the router maps it to an HTTP status.
    """
    if pin_type not in PIN_TYPES:
        raise ValueError(f"Unsupported pin_type '{pin_type}' — must be one of {PIN_TYPES}.")

    result = _execute_pin(db, pin_type, source_id, query_params, pinned_by, dashboard.workspace_id)

    max_position_row = (
        db.query(DashboardPin.position)
        .filter(DashboardPin.dashboard_id == dashboard.id)
        .order_by(DashboardPin.position.desc())
        .first()
    )
    next_position = (max_position_row[0] + 1) if max_position_row else 0

    pin = DashboardPin(
        dashboard_id=dashboard.id,
        pinned_by=pinned_by,
        title=title,
        pin_type=pin_type,
        source_id=source_id,
        query_params=query_params or {},
        cached_result=result,
        last_refreshed_at=datetime.now(timezone.utc),
        position=next_position,
    )
    db.add(pin)
    db.commit()
    db.refresh(pin)
    return pin


def remove_pin(db: Session, pin: DashboardPin) -> None:
    db.delete(pin)
    db.commit()


def refresh_pin(db: Session, pin: DashboardPin) -> DashboardPin:
    """
    Unlike add_pin, a failed refresh doesn't raise — it overwrites
    cached_result with an error shape and still advances
    last_refreshed_at, mirroring AlertRule.last_checked_at updating on
    every evaluation regardless of outcome (Day 20). This is what lets
    refresh_dashboard/the daily sweep continue past one broken pin
    instead of aborting the whole batch.
    """
    try:
        result = _execute_pin(
            db, pin.pin_type, pin.source_id, pin.query_params, pin.pinned_by, pin.dashboard.workspace_id
        )
        pin.cached_result = result
    except Exception as e:
        pin.cached_result = {"error": str(e)}

    pin.last_refreshed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(pin)
    return pin


def refresh_dashboard(db: Session, dashboard: Dashboard) -> list[DashboardPin]:
    for pin in dashboard.pins:
        refresh_pin(db, pin)
    return dashboard.pins
