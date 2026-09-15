# WHY THIS FILE EXISTS:
# Three tasks: check_dataset_alerts_task (Beat-independent, enqueued
# directly by dataset.py right after a successful upload),
# daily_alert_sweep_task (Beat, 7am UTC), and run_single_alert_check_task
# (the manual "test this one rule" trigger behind POST /alerts/{id}/check
# — not named in the original outline, but POST .../check needs a task
# to run async against, same as every other manual-trigger endpoint in
# this app). All three funnel through _finalize(), which persists an
# AlertHistory row per check performed and sends an email per trigger.
#
# Unlike Day 19's ScheduledReport.next_run_at, AlertRule's
# last_checked_at/last_triggered_at don't drive any future timing
# decision — they're purely observational. So a manual check updates
# them exactly like an automatic one; there's no drift risk to guard
# against here.

from datetime import datetime, timezone

from app.database import SessionLocal
from app.models.alert_history import AlertHistory
from app.models.alert_rule import AlertRule
from app.services import anomaly_service, email_service
from app.services.access_control import get_dataset_for_user
from app.services.storage_service import load_dataframe
from app.worker import celery_app


def _finalize(db, results: list[dict]) -> dict:
    """
    results: [{rule, alert_type, triggered, actual_value, z_score}, ...]
    (anomaly_service's output, annotated with which AlertRule each came
    from). Persists one AlertHistory row per entry, emails each trigger,
    updates last_checked_at/last_triggered_at once per distinct rule.
    """
    now = datetime.now(timezone.utc)
    checked_rule_ids: set[int] = set()
    triggered_rule_ids: set[int] = set()
    summary = []

    for r in results:
        rule = r["rule"]
        checked_rule_ids.add(rule.id)

        email_sent = False
        error = None
        if r["triggered"]:
            triggered_rule_ids.add(rule.id)
            try:
                email_service.send_alert_email(
                    recipients=rule.recipients,
                    rule_name=rule.name,
                    dataset_name=rule.dataset.filename,
                    column=rule.column,
                    metric=rule.metric,
                    condition=rule.condition,
                    threshold=rule.threshold,
                    actual_value=r["actual_value"],
                    alert_type=r["alert_type"],
                    z_score=r["z_score"],
                )
                email_sent = True
            except Exception as e:
                error = str(e)

        db.add(
            AlertHistory(
                alert_rule_id=rule.id,
                triggered=r["triggered"],
                actual_value=r["actual_value"],
                z_score=r["z_score"],
                alert_type=r["alert_type"],
                email_sent=email_sent,
                error=error,
            )
        )
        summary.append(
            {
                "rule_id": rule.id,
                "alert_type": r["alert_type"],
                "triggered": r["triggered"],
                "actual_value": r["actual_value"],
                "z_score": r["z_score"],
                "email_sent": email_sent,
                "email_error": error,
            }
        )

    for rule_id in checked_rule_ids:
        db.query(AlertRule).filter(AlertRule.id == rule_id).update({"last_checked_at": now})
    for rule_id in triggered_rule_ids:
        db.query(AlertRule).filter(AlertRule.id == rule_id).update({"last_triggered_at": now})
    db.commit()

    return {"checked_rules": len(checked_rule_ids), "triggered": len(triggered_rule_ids), "results": summary}


@celery_app.task(name="alert_tasks.check_dataset_alerts")
def check_dataset_alerts_task(dataset_id: int) -> dict:
    """Enqueued by dataset.py right after a successful upload — non-blocking, the upload response doesn't wait for this."""
    db = SessionLocal()
    try:
        results = anomaly_service.run_alerts_for_dataset(dataset_id, db, frequency_filter=("on_upload", "both"))
        return _finalize(db, results)
    finally:
        db.close()


@celery_app.task(name="alert_tasks.daily_alert_sweep")
def daily_alert_sweep_task() -> dict:
    db = SessionLocal()
    try:
        dataset_ids = [
            row[0]
            for row in db.query(AlertRule.dataset_id)
            .filter(AlertRule.is_active.is_(True), AlertRule.frequency.in_(("daily", "both")))
            .distinct()
            .all()
        ]
        all_results = []
        for dataset_id in dataset_ids:
            all_results.extend(
                anomaly_service.run_alerts_for_dataset(dataset_id, db, frequency_filter=("daily", "both"))
            )
        return _finalize(db, all_results)
    finally:
        db.close()


@celery_app.task(name="alert_tasks.run_single_alert_check")
def run_single_alert_check_task(alert_rule_id: int) -> dict:
    """Backs POST /alerts/{id}/check — manual test trigger for one specific rule."""
    db = SessionLocal()
    try:
        rule = db.query(AlertRule).filter(AlertRule.id == alert_rule_id).first()
        if not rule:
            raise ValueError(f"Alert rule {alert_rule_id} not found.")

        dataset = get_dataset_for_user(db, rule.dataset_id, rule.created_by)
        df = load_dataframe(dataset.file_path)
        results = [{"rule": rule, **r} for r in anomaly_service.evaluate_alert_rule(rule, df, db)]
        return _finalize(db, results)
    finally:
        db.close()
