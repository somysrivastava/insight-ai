# WHY THIS FILE EXISTS:
# Two Celery Beat entries (registered in app/worker.py's beat_schedule)
# point here: poll_due_reports_task (every minute) and
# cleanup_expired_exports_task (daily, 3am UTC). Beat only ever knows
# about these two static entries — it has no idea how many
# ScheduledReport rows exist or when each one is due; that's what
# poll_due_reports_task figures out by querying the database itself.
#
# DOUBLE-SEND PREVENTION: poll_due_reports_task claims a due row with a
# conditional UPDATE (guarded on the exact next_run_at it read) in the
# same step it decides to enqueue work for it — not after the work
# finishes. If an export runs long enough to still be in flight at the
# next minute's poll, that row's next_run_at has already moved, so the
# WHERE clause no longer matches and the second poll skips it. This is
# also what makes "missed runs fire once, don't backfill" fall out for
# free: the new next_run_at is always computed from *now* (the claim
# moment), never from the stale value, so a report that was due 3 days
# ago (server was down) fires once, and its next occurrence is computed
# from today.

from datetime import datetime, timezone

from sqlalchemy import update

from app.database import SessionLocal
from app.models import ExportJob
from app.models.scheduled_report import ScheduledReport
from app.services import email_service
from app.services.schedule_service import compute_next_run_at
from app.services.storage_service import get_storage_backend
from app.tasks.export_tasks import run_dataset_export, run_join_query_export, run_report_export
from app.worker import celery_app


def _summary_from_doc(doc: dict | None) -> str | None:
    if not doc:
        return None
    if doc.get("narrative"):
        return doc["narrative"].get("headline")
    return doc.get("answer")


@celery_app.task(name="scheduled_tasks.poll_due_reports")
def poll_due_reports_task() -> dict:
    db = SessionLocal()
    claimed = 0
    try:
        now = datetime.now(timezone.utc)
        due = (
            db.query(ScheduledReport)
            .filter(ScheduledReport.is_active.is_(True), ScheduledReport.next_run_at <= now)
            .all()
        )

        for schedule in due:
            guard_next_run_at = schedule.next_run_at
            new_next_run_at = compute_next_run_at(
                schedule.frequency, schedule.hour, schedule.day_of_week, schedule.day_of_month, after=now
            )
            result = db.execute(
                update(ScheduledReport)
                .where(ScheduledReport.id == schedule.id, ScheduledReport.next_run_at == guard_next_run_at)
                .values(next_run_at=new_next_run_at)
            )
            db.commit()

            if result.rowcount == 1:
                claimed += 1
                run_scheduled_report_task.delay(schedule.id)

        return {"due": len(due), "claimed": claimed}
    finally:
        db.close()


@celery_app.task(name="scheduled_tasks.run_scheduled_report")
def run_scheduled_report_task(schedule_id: int, is_manual_trigger: bool = False) -> dict:
    db = SessionLocal()
    try:
        schedule = db.query(ScheduledReport).filter(ScheduledReport.id == schedule_id).first()
        if not schedule:
            raise ValueError(f"Scheduled report {schedule_id} not found.")

        if schedule.source_type == "dataset_query":
            export_job, doc = run_dataset_export(
                db, schedule.source_id, schedule.created_by, "query", schedule.export_format, schedule.question, None
            )
        elif schedule.source_type == "join_query":
            export_job, doc = run_join_query_export(
                db, schedule.source_id, schedule.created_by, schedule.question, schedule.export_format
            )
        elif schedule.source_type == "report":
            export_job, doc = run_report_export(db, schedule.source_id, schedule.created_by, schedule.export_format)
        else:
            raise ValueError(f"Unsupported source_type: {schedule.source_type}")

        email_error = None
        if export_job.status == "success":
            try:
                file_bytes = get_storage_backend("exports").load(export_job.file_path)
                filename = export_job.file_path.rsplit("/", 1)[-1]
                email_service.send_export_email(
                    recipients=schedule.recipients,
                    schedule_name=schedule.name,
                    export_format=schedule.export_format,
                    file_bytes=file_bytes,
                    filename=filename,
                    summary=_summary_from_doc(doc),
                )
            except Exception as e:
                email_error = str(e)

        # A manual "run now" (POST /schedules/{id}/run) is for testing —
        # it shouldn't move last_run_at, which should only reflect a
        # real scheduled firing.
        if not is_manual_trigger:
            schedule.last_run_at = datetime.now(timezone.utc)
            db.commit()

        return {
            "schedule_id": schedule.id,
            "export_id": export_job.id,
            "export_status": export_job.status,
            "export_error": export_job.error,
            "email_sent": export_job.status == "success" and email_error is None,
            "email_error": email_error,
        }
    finally:
        db.close()


@celery_app.task(name="scheduled_tasks.cleanup_expired_exports")
def cleanup_expired_exports_task() -> dict:
    """Deferred from Day 18 — expiry was enforced only at request time
    (GET /exports/{id} returning 410) until Beat existed to run this."""
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        expired = db.query(ExportJob).filter(ExportJob.expires_at < now).all()
        backend = get_storage_backend("exports")

        for export_job in expired:
            if export_job.file_path:
                backend.delete(export_job.file_path)
            db.delete(export_job)
        db.commit()

        return {"deleted": len(expired)}
    finally:
        db.close()
