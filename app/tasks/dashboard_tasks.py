# WHY THIS FILE EXISTS:
# Three tasks, same reasoning as Day 20's alert_tasks.py: refresh_dashboard_task
# backs POST /dashboards/{id}/refresh, daily_dashboard_refresh_task is the
# Beat entry (6am UTC, active dashboards only), and refresh_single_pin_task
# is the manual "refresh just this one pin" trigger behind
# POST /dashboards/{id}/pins/{pin_id}/refresh — not named in the original
# outline, but every other manual-trigger endpoint in this app
# (POST /schedules/{id}/run, POST /alerts/{id}/check) needs its own task
# to run against, and this is no different.

from app.database import SessionLocal
from app.models.dashboard import Dashboard
from app.models.dashboard_pin import DashboardPin
from app.services import dashboard_service
from app.worker import celery_app


@celery_app.task(name="dashboard_tasks.refresh_dashboard")
def refresh_dashboard_task(dashboard_id: int) -> dict:
    """Backs POST /dashboards/{id}/refresh."""
    db = SessionLocal()
    try:
        dashboard = db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
        if not dashboard:
            raise ValueError(f"Dashboard {dashboard_id} not found.")
        pins = dashboard_service.refresh_dashboard(db, dashboard)
        return {
            "dashboard_id": dashboard_id,
            "refreshed_pins": len(pins),
            "failed_pins": sum(1 for p in pins if isinstance(p.cached_result, dict) and "error" in p.cached_result),
        }
    finally:
        db.close()


@celery_app.task(name="dashboard_tasks.refresh_single_pin")
def refresh_single_pin_task(pin_id: int) -> dict:
    """Backs POST /dashboards/{id}/pins/{pin_id}/refresh."""
    db = SessionLocal()
    try:
        pin = db.query(DashboardPin).filter(DashboardPin.id == pin_id).first()
        if not pin:
            raise ValueError(f"Dashboard pin {pin_id} not found.")
        dashboard_service.refresh_pin(db, pin)
        return {
            "pin_id": pin.id,
            "last_refreshed_at": pin.last_refreshed_at.isoformat() if pin.last_refreshed_at else None,
            "failed": isinstance(pin.cached_result, dict) and "error" in pin.cached_result,
        }
    finally:
        db.close()


@celery_app.task(name="dashboard_tasks.daily_dashboard_refresh")
def daily_dashboard_refresh_task() -> dict:
    """Beat, 6am UTC — refreshes every pin on every active dashboard."""
    db = SessionLocal()
    try:
        dashboards = db.query(Dashboard).filter(Dashboard.is_active.is_(True)).all()
        total_pins = 0
        failed_pins = 0
        for dashboard in dashboards:
            pins = dashboard_service.refresh_dashboard(db, dashboard)
            total_pins += len(pins)
            failed_pins += sum(1 for p in pins if isinstance(p.cached_result, dict) and "error" in p.cached_result)
        return {"refreshed_dashboards": len(dashboards), "refreshed_pins": total_pins, "failed_pins": failed_pins}
    finally:
        db.close()
