import io                          # NEW — needed to convert bytes to file-like object for pandas
import os               # REMOVED — no longer writing to local disk
from app.models.user import User
from app.services.auth_service import get_current_user
from app.services.s3_service import (    # NEW — import S3 functions
    upload_file_to_s3,
    download_file_from_s3,
    generate_presigned_url,
    get_s3_key,
)
import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.dataset import Dataset

import traceback

router = APIRouter()

UPLOAD_FOLDER = "app/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@router.post("/upload")
async def upload_dataset(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # CHANGED — read file into memory as bytes instead of writing to disk
    file_bytes = await file.read()

    # NEW — generate S3 key: uploads/{user_id}/{filename}
    s3_key = get_s3_key(current_user.id, file.filename)

    # NEW — upload bytes to S3
    try:
        upload_file_to_s3(file_bytes, s3_key)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to upload to S3: {str(e)}")

    # CHANGED — parse from bytes instead of from disk file
    try:
        df = pd.read_csv(io.BytesIO(file_bytes))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid CSV file: {str(e)}")

    new_dataset = Dataset(
        user_id=current_user.id,
        filename=file.filename,
        file_path=s3_key,          # CHANGED — store S3 key instead of local path
        row_count=len(df),
        column_count=len(df.columns),
    )
    db.add(new_dataset)
    db.commit()
    db.refresh(new_dataset)

    return {
        "message": "File uploaded successfully to S3",
        "dataset": {
            "id": new_dataset.id,
            "filename": new_dataset.filename,
            "rows": new_dataset.row_count,
            "columns": new_dataset.column_count,
            "s3_key": s3_key,      # NEW — return s3 key in response
            "uploaded_at": new_dataset.created_at,
        }
    }


@router.get("/datasets/")
def list_datasets(db: Session = Depends(get_db)):
    # UNCHANGED
    datasets = db.query(Dataset).all()
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
    current_user: User = Depends(get_current_user),  # NEW — added auth
):
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # CHANGED — download from S3 instead of reading from disk
    try:
        file_bytes = download_file_from_s3(dataset.file_path)
        df = pd.read_csv(io.BytesIO(file_bytes))
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


# NEW ENDPOINT — generate presigned download URL
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
        url = generate_presigned_url(dataset.file_path, expires_in=3600)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not generate download URL: {str(e)}")

    return {
        "download_url": url,
        "expires_in_seconds": 3600,
        "filename": dataset.filename,
    }