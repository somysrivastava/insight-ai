import traceback
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.models.bulk_upload_job import BulkUploadJob
from app.models.workspace_member import WorkspaceMember
from app.rate_limiter import limiter
from app.schemas.bulk_upload import BulkUploadJobResponse, BulkUploadSubmitResponse
from app.services import dataset_service
from app.services.access_control import require_workspace_access, require_workspace_membership
from app.services.auth_service import get_current_user
from app.services.storage_service import get_storage_backend, get_storage_key
from app.tasks.bulk_tasks import process_bulk_upload_task

router = APIRouter(prefix="/bulk-upload", tags=["Bulk Upload"])

MAX_FILES = 50
MAX_TOTAL_BYTES = 100 * 1024 * 1024  # 100MB


@router.post("", response_model=BulkUploadSubmitResponse, status_code=202)
@limiter.limit("10/hour")
async def submit_bulk_upload(
    request: Request,
    response: Response,
    files: list[UploadFile] = File(...),
    workspace_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Accepts up to 50 files (100MB total) in one request, processes each
    independently and asynchronously — poll GET /bulk-upload/{job_id}
    for progress and per-file results. Multi-sheet Excel files create
    one dataset per sheet, same as a single POST /upload.
    """
    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required.")
    if len(files) > MAX_FILES:
        raise HTTPException(
            status_code=400, detail=f"Too many files — max {MAX_FILES} per request, got {len(files)}."
        )

    resolved_workspace_id = require_workspace_access(db, current_user.id, workspace_id)

    contents: list[tuple[str, bytes]] = []
    total_bytes = 0
    for f in files:
        file_bytes = await f.read()
        total_bytes += len(file_bytes)
        if total_bytes > MAX_TOTAL_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Total upload size exceeds the {MAX_TOTAL_BYTES // (1024 * 1024)}MB limit.",
            )
        try:
            dataset_service.validate_upload_content_type(f.content_type, f.filename)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        contents.append((f.filename, file_bytes))

    job = BulkUploadJob(
        workspace_id=resolved_workspace_id,
        created_by=current_user.id,
        status="pending",
        total_files=0,
        succeeded=0,
        failed=0,
        results=[],
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Celery can't carry raw file bytes as a task argument (Redis/JSON
    # task serialization) — stage each file under a temp storage key
    # first, hand the task only lightweight references. Index-prefixed
    # so two files with the identical name in one request don't
    # collide before either is processed.
    backend = get_storage_backend("bulk_uploads")
    file_refs = []
    for i, (filename, file_bytes) in enumerate(contents):
        temp_key = get_storage_key(f"job_{job.id}", f"{i}_{filename}")
        try:
            backend.save(file_bytes, temp_key)
        except Exception as e:
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Failed to stage '{filename}' for processing: {str(e)}")
        file_refs.append({"filename": filename, "storage_key": temp_key})

    process_bulk_upload_task.delay(job.id, file_refs)
    return BulkUploadSubmitResponse(job_id=job.id)


@router.get("/{job_id}", response_model=BulkUploadJobResponse)
def get_bulk_upload_job(job_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    job = db.query(BulkUploadJob).filter(BulkUploadJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Bulk upload job not found")
    require_workspace_membership(db, job.workspace_id, current_user.id)
    return job


@router.get("", response_model=list[BulkUploadJobResponse])
def list_bulk_upload_jobs(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Lists bulk upload jobs across every workspace the current user belongs to."""
    return (
        db.query(BulkUploadJob)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == BulkUploadJob.workspace_id)
        .filter(WorkspaceMember.user_id == current_user.id)
        .order_by(BulkUploadJob.created_at.desc())
        .all()
    )
