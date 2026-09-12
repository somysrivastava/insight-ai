import io
import traceback

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.dataset import Dataset
from app.models.user import User
from app.services.auth_service import get_current_user
from app.services.storage_service import get_storage_backend, get_storage_key

router = APIRouter()


@router.post("/upload")
async def upload_dataset(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    file_bytes = await file.read()
    storage_key = get_storage_key(current_user.id, file.filename)

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
        filename=file.filename,
        file_path=storage_key,
        row_count=len(df),
        column_count=len(df.columns),
    )
    db.add(new_dataset)
    db.commit()
    db.refresh(new_dataset)

    return {
        "message": "File uploaded successfully",
        "dataset": {
            "id": new_dataset.id,
            "filename": new_dataset.filename,
            "rows": new_dataset.row_count,
            "columns": new_dataset.column_count,
            "storage_key": storage_key,
            "uploaded_at": new_dataset.created_at,
        }
    }


@router.get("/datasets/")
def list_datasets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    datasets = db.query(Dataset).filter(Dataset.user_id == current_user.id).all()
    return {
        "datasets": [
            {
                "id": d.id,
                "filename": d.filename,
                "rows": d.row_count,
                "columns": d.column_count,
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
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    if dataset.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

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
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    if dataset.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

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
