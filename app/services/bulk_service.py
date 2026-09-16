# WHY THIS FILE EXISTS:
# Processes one BulkUploadJob's files one at a time, each independently
# — a bad file (bad CSV, bad Excel, a storage failure) marks just that
# file's result entry as failed and moves on, never aborting the whole
# job. Reuses dataset_service.create_datasets_from_file for the actual
# per-file logic — no duplicated upload logic here. Deliberately
# doesn't touch Celery (no check_dataset_alerts_task calls) — that's
# fired by the task layer (app/tasks/bulk_tasks.py) after this
# finishes, same layering as dashboard_service.py/version_service.py.

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.bulk_upload_job import BulkUploadJob
from app.services import dataset_service
from app.services.storage_service import get_storage_backend


def process_bulk_upload(db: Session, job: BulkUploadJob, file_refs: list[dict]) -> BulkUploadJob:
    """
    file_refs: [{"filename": str, "storage_key": str}, ...] — each
    storage_key points at a temporary copy the router saved before this
    job was enqueued (a Celery task argument can't carry raw file
    bytes). Each temp file is deleted here once processed, success or
    failure — on success the real content already lives at the
    dataset's own permanent storage key.
    """
    backend = get_storage_backend("bulk_uploads")
    job.status = "processing"
    db.commit()

    for ref in file_refs:
        filename = ref["filename"]
        try:
            file_bytes = backend.load(ref["storage_key"])
            created = dataset_service.create_datasets_from_file(
                db, file_bytes, filename, job.workspace_id, job.created_by
            )
        except Exception as e:
            job.results = [
                *job.results,
                {"filename": filename, "sheet_name": None, "status": "failed", "dataset_id": None, "error": str(e)},
            ]
            job.failed += 1
            job.total_files += 1
        else:
            for dataset in created:
                job.results = [
                    *job.results,
                    {
                        "filename": filename,
                        "sheet_name": dataset.sheet_name,
                        "status": "success",
                        "dataset_id": dataset.id,
                        "error": None,
                    },
                ]
                job.succeeded += 1
                job.total_files += 1
        finally:
            backend.delete(ref["storage_key"])

        db.commit()

    job.status = "completed" if job.failed == 0 else "failed" if job.succeeded == 0 else "partially_failed"
    job.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)
    return job
