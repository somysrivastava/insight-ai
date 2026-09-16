import io
import traceback
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Dataset, User
from app.models.workspace_member import WorkspaceMember
from app.schemas.export import DatasetExportRequest
from app.schemas.jobs import JobSubmitResponse
from app.services.access_control import require_dataset_access, require_workspace_access
from app.services.auth_service import get_current_user
from app.services import version_service
from app.services.job_service import record_job_owner
from app.services.storage_service import get_storage_backend, get_storage_key
from app.tasks.alert_tasks import check_dataset_alerts_task
from app.tasks.export_tasks import export_dataset_task

router = APIRouter()


def _sanitize_for_key(name: str) -> str:
    """Keeps sheet/file names from introducing path separators into a storage key."""
    return name.strip().replace("/", "_").replace("\\", "_")


@router.post("/upload")
async def upload_dataset(
    file: UploadFile = File(...),
    workspace_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Uploads a CSV or Excel file. A multi-sheet .xlsx creates one Dataset
    row per sheet, each independently queryable — every existing service
    (analytics/cleaning/reports/ai) already handles .csv without changes,
    so each sheet is normalized to .csv in storage regardless of the
    original upload format.

    workspace_id is optional and defaults to the caller's own workspace
    — the only real option today since every user has exactly one
    (Day 16). Becomes a meaningful choice once a user can belong to more
    than one workspace.
    """
    file_bytes = await file.read()
    resolved_workspace_id = require_workspace_access(db, current_user.id, workspace_id)

    if file.filename.lower().endswith((".xlsx", ".xls")):
        try:
            sheets = pd.read_excel(io.BytesIO(file_bytes), sheet_name=None)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid Excel file: {str(e)}")

        if not sheets:
            raise HTTPException(status_code=400, detail="Excel file has no sheets.")

        base_name = Path(file.filename).stem
        backend = get_storage_backend()
        created = []

        for sheet_name, df in sheets.items():
            storage_key = get_storage_key(
                resolved_workspace_id, f"{_sanitize_for_key(base_name)}__{_sanitize_for_key(sheet_name)}.csv"
            )
            try:
                backend.save(df.to_csv(index=False).encode("utf-8"), storage_key)
            except Exception as e:
                traceback.print_exc()
                raise HTTPException(
                    status_code=500, detail=f"Failed to store sheet '{sheet_name}': {str(e)}"
                )

            new_dataset = Dataset(
                user_id=current_user.id,
                workspace_id=resolved_workspace_id,
                filename=file.filename,
                sheet_name=sheet_name,
                file_path=storage_key,
                row_count=len(df),
                column_count=len(df.columns),
            )
            db.add(new_dataset)
            created.append(new_dataset)

        db.commit()
        for d in created:
            db.refresh(d)
            # Day 23 — version 1 of this dataset's history, reusing the
            # file already saved above (no duplicate save).
            version_service.create_initial_version(db, d, current_user.id)
            # Non-blocking — the upload response doesn't wait for alert
            # rules to be checked. One sheet = one dataset_id = its own
            # independent set of watching rules.
            check_dataset_alerts_task.delay(d.id)

        return {
            "message": f"Excel file uploaded successfully — {len(created)} sheet(s) created as separate datasets",
            "datasets": [
                {
                    "id": d.id,
                    "filename": d.filename,
                    "sheet_name": d.sheet_name,
                    "rows": d.row_count,
                    "columns": d.column_count,
                    "workspace_id": d.workspace_id,
                    "uploaded_at": d.created_at,
                }
                for d in created
            ],
        }

    storage_key = get_storage_key(resolved_workspace_id, file.filename)

    try:
        get_storage_backend().save(file_bytes, storage_key)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to store file: {str(e)}")

    try:
        df = pd.read_csv(io.BytesIO(file_bytes))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid CSV file: {str(e)}")

    new_dataset = Dataset(
        user_id=current_user.id,
        workspace_id=resolved_workspace_id,
        filename=file.filename,
        file_path=storage_key,
        row_count=len(df),
        column_count=len(df.columns),
    )
    db.add(new_dataset)
    db.commit()
    db.refresh(new_dataset)
    version_service.create_initial_version(db, new_dataset, current_user.id)  # Day 23
    check_dataset_alerts_task.delay(new_dataset.id)  # non-blocking, see above

    return {
        "message": "File uploaded successfully",
        "dataset": {
            "id": new_dataset.id,
            "filename": new_dataset.filename,
            "rows": new_dataset.row_count,
            "columns": new_dataset.column_count,
            "workspace_id": new_dataset.workspace_id,
            "storage_key": storage_key,
            "uploaded_at": new_dataset.created_at,
        }
    }


@router.get("/datasets/")
def list_datasets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lists datasets across every workspace the current user belongs to, not just their own uploads."""
    datasets = (
        db.query(Dataset)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Dataset.workspace_id)
        .filter(WorkspaceMember.user_id == current_user.id)
        .all()
    )
    return {
        "datasets": [
            {
                "id": d.id,
                "filename": d.filename,
                "sheet_name": d.sheet_name,
                "rows": d.row_count,
                "columns": d.column_count,
                "workspace_id": d.workspace_id,
                "uploaded_at": d.created_at,
            }
            for d in datasets
        ]
    }


@router.get("/datasets/{dataset_id}/summary")
def get_dataset_summary(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset = require_dataset_access(db, dataset_id, current_user.id)

    try:
        file_bytes = get_storage_backend().load(dataset.file_path)
        df = pd.read_csv(io.BytesIO(file_bytes))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Dataset file not found in storage")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not read dataset: {str(e)}")

    return {
        "id": dataset.id,
        "filename": dataset.filename,
        "sheet_name": dataset.sheet_name,
        "rows": len(df),
        "columns": len(df.columns),
        "column_name": list(df.columns),
        "missing_values": df.isnull().sum().to_dict(),
        "data_types": {col: str(dtype) for col, dtype in df.dtypes.items()},
    }


@router.get("/datasets/{dataset_id}/download")
def get_download_url(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset = require_dataset_access(db, dataset_id, current_user.id)

    try:
        url = get_storage_backend().url_for(dataset.file_path, expires_in=3600)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not generate download URL: {str(e)}")

    if url is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "Direct download links aren't available on the local storage "
                "backend. Use GET /datasets/{id}/summary to read the file instead."
            ),
        )

    return {
        "download_url": url,
        "expires_in_seconds": 3600,
        "filename": dataset.filename,
    }


@router.post("/datasets/{dataset_id}/export", response_model=JobSubmitResponse, status_code=202)
def export_dataset(
    dataset_id: int,
    request: DatasetExportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Exports a query result (source="query"), or an analytics result
    (source="insights"|"trends"|"breakdown") as CSV/Excel/PDF. Async
    only — poll GET /jobs/{task_id}, then GET /exports/{export_id} from
    its result once it succeeds.
    """
    require_dataset_access(db, dataset_id, current_user.id)

    task = export_dataset_task.delay(
        dataset_id, current_user.id, request.source, request.format, request.question, request.group_by
    )
    record_job_owner(task.id, current_user.id)
    return JobSubmitResponse(task_id=task.id)
