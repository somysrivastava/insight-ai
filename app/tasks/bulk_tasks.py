# WHY THIS FILE EXISTS:
# One task, process_bulk_upload_task. The router already validated the
# request (file count/size caps, workspace access), saved each file to
# temporary storage, and created the BulkUploadJob row before
# enqueueing this. Fires check_dataset_alerts_task per successfully
# created dataset after bulk_service.process_bulk_upload finishes —
# kept here rather than in bulk_service.py, so that file stays
# Celery-agnostic like dashboard_service.py/version_service.py.

from app.database import SessionLocal
from app.models.bulk_upload_job import BulkUploadJob
from app.services import bulk_service
from app.tasks.alert_tasks import check_dataset_alerts_task
from app.worker import celery_app


@celery_app.task(name="bulk_tasks.process_bulk_upload")
def process_bulk_upload_task(job_id: int, file_refs: list[dict]) -> dict:
    db = SessionLocal()
    try:
        job = db.query(BulkUploadJob).filter(BulkUploadJob.id == job_id).first()
        if not job:
            raise ValueError(f"Bulk upload job {job_id} not found.")

        job = bulk_service.process_bulk_upload(db, job, file_refs)

        for entry in job.results:
            if entry["status"] == "success":
                check_dataset_alerts_task.delay(entry["dataset_id"])

        return {"job_id": job.id, "status": job.status, "succeeded": job.succeeded, "failed": job.failed}
    finally:
        db.close()
