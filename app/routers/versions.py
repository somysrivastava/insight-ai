from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas.version import DatasetVersionResponse
from app.services import dashboard_service, dataset_service, version_service
from app.services.access_control import require_dataset_access
from app.services.auth_service import get_current_user
from app.services.storage_service import get_storage_backend
from app.tasks.alert_tasks import check_dataset_alerts_task
from app.tasks.dashboard_tasks import refresh_dashboard_task

router = APIRouter(prefix="/datasets", tags=["Dataset Versions"])


def _fire_version_triggers(db: Session, dataset_id: int) -> None:
    """
    Same non-blocking pattern as a fresh upload (dataset.py) — the
    response doesn't wait for either. check_dataset_alerts_task is what
    actually resolves the Day 20 on_upload gap (ADR-015): a push now
    means "new data landed for this dataset_id," so on_upload rules
    watching it can finally fire organically.
    """
    check_dataset_alerts_task.delay(dataset_id)
    for dashboard_id in dashboard_service.find_dashboards_pinning_dataset(db, dataset_id):
        refresh_dashboard_task.delay(dashboard_id)


@router.post("/{dataset_id}/versions", response_model=DatasetVersionResponse, status_code=201)
async def push_version(
    dataset_id: int,
    file: UploadFile = File(...),
    change_summary: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Pushes new data into an existing dataset. CSV or single-sheet Excel only — a version is one sheet's lineage."""
    dataset = require_dataset_access(db, dataset_id, current_user.id)
    file_bytes = await file.read()

    try:
        dataset_service.validate_upload_content_type(file.content_type, file.filename)
        version = version_service.push_new_version(
            db, dataset, file_bytes, file.filename, current_user.id, change_summary
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Current version's file not found in storage")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    _fire_version_triggers(db, dataset_id)
    return version


@router.get("/{dataset_id}/versions", response_model=list[DatasetVersionResponse])
def list_versions(dataset_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    require_dataset_access(db, dataset_id, current_user.id)
    return version_service.get_versions(db, dataset_id)


@router.get("/{dataset_id}/versions/{version_number}", response_model=DatasetVersionResponse)
def get_version(
    dataset_id: int, version_number: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    require_dataset_access(db, dataset_id, current_user.id)
    version = version_service.get_version(db, dataset_id, version_number)
    if not version:
        raise HTTPException(status_code=404, detail=f"Version {version_number} not found for this dataset.")
    return version


@router.get("/{dataset_id}/versions/{version_number}/download")
def download_version(
    dataset_id: int, version_number: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Streams the file directly (like Day 18's exports), not a JSON download_url — the only form that
    actually works under the current local storage backend (see the original /datasets/{id}/download)."""
    require_dataset_access(db, dataset_id, current_user.id)
    version = version_service.get_version(db, dataset_id, version_number)
    if not version:
        raise HTTPException(status_code=404, detail=f"Version {version_number} not found for this dataset.")

    try:
        file_bytes = get_storage_backend().load(version.file_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Version file not found in storage")

    filename = Path(version.file_path).name
    return Response(
        content=file_bytes,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{dataset_id}/versions/{version_number}/rollback", response_model=DatasetVersionResponse, status_code=201)
def rollback_version(
    dataset_id: int, version_number: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Creates a new version whose content copies `version_number`'s — version numbers only ever go up."""
    dataset = require_dataset_access(db, dataset_id, current_user.id)
    target = version_service.get_version(db, dataset_id, version_number)
    if not target:
        raise HTTPException(status_code=404, detail=f"Version {version_number} not found for this dataset.")

    try:
        version = version_service.rollback_version(db, dataset, target, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    _fire_version_triggers(db, dataset_id)
    return version
