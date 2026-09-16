import io
import traceback
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Dataset, User
from app.models.workspace_member import WorkspaceMember
from app.rate_limiter import limiter
from app.schemas.export import DatasetExportRequest
from app.schemas.jobs import JobSubmitResponse
from app.services import dataset_service
from app.services.access_control import require_dataset_access, require_workspace_access
from app.services.auth_service import get_current_user
from app.services.job_service import record_job_owner
from app.services.storage_service import get_storage_backend
from app.tasks.alert_tasks import check_dataset_alerts_task
from app.tasks.export_tasks import export_dataset_task

router = APIRouter()


@router.post("/upload")
@limiter.limit("50/hour")
async def upload_dataset(
    request: Request,
    response: Response,
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

    try:
        dataset_service.validate_upload_content_type(file.content_type, file.filename)
        created = dataset_service.create_datasets_from_file(
            db, file_bytes, file.filename, resolved_workspace_id, current_user.id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to store file: {str(e)}")

    for d in created:
        # Non-blocking — the upload response doesn't wait for alert
        # rules to be checked. One sheet = one dataset_id = its own
        # independent set of watching rules.
        check_dataset_alerts_task.delay(d.id)

    # A multi-sheet Excel (even a single-sheet one) sets sheet_name;
    # a plain CSV never does — distinguishes the response shape without
    # re-checking the original filename's extension here too.
    if len(created) > 1 or created[0].sheet_name is not None:
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

    new_dataset = created[0]
    return {
        "message": "File uploaded successfully",
        "dataset": {
            "id": new_dataset.id,
            "filename": new_dataset.filename,
            "rows": new_dataset.row_count,
            "columns": new_dataset.column_count,
            "workspace_id": new_dataset.workspace_id,
            "storage_key": new_dataset.file_path,
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
