from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ExportJob, User
from app.services.access_control import require_workspace_membership
from app.services.auth_service import get_current_user
from app.services.storage_service import get_storage_backend

router = APIRouter(prefix="/exports", tags=["Exports"])

_CONTENT_TYPES = {
    "csv": "text/csv",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
}


@router.get("/{export_id}")
def download_export(export_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Streams a previously generated export file directly (not a
    JSON-wrapped download_url) — LocalStorageBackend has no presigned-URL
    concept, so this is the only way a local export is actually
    downloadable. Swapping STORAGE_BACKEND=s3 later, this could instead
    302-redirect to a presigned URL; not needed while local is the only
    active backend.
    """
    export_job = db.query(ExportJob).filter(ExportJob.id == export_id).first()
    if not export_job:
        raise HTTPException(status_code=404, detail="Export not found")

    require_workspace_membership(db, export_job.workspace_id, current_user.id)

    if export_job.status == "failed":
        raise HTTPException(status_code=422, detail=f"This export failed: {export_job.error}")

    if datetime.now(timezone.utc) > export_job.expires_at:
        raise HTTPException(status_code=410, detail="This export has expired.")

    try:
        file_bytes = get_storage_backend("exports").load(export_job.file_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Export file not found in storage")

    filename = export_job.file_path.rsplit("/", 1)[-1]
    return Response(
        content=file_bytes,
        media_type=_CONTENT_TYPES[export_job.format],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
