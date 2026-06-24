import os
import shutil

from app.models.user import User
from app.services.auth_service import get_current_user

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import (
    get_db,  # get_db is the dependency that opens a database session for each request
)
from app.models.dataset import (
    Dataset,  # We need the Dataset model to create and query rows
)

router = APIRouter()

UPLOAD_FOLDER = "app/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@router.post("/upload")
async def upload_dataset(file: UploadFile = File(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Depends(get_db) tells FastAPI: call get_db() and inject the session as "db"
    # Every request gets its own fresh session

    file_path = f"{UPLOAD_FOLDER}/{file.filename}"

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    df = pd.read_csv(file_path)

    new_dataset = Dataset(
        user_id=current_user.id,
        filename=file.filename,
        file_path=file_path,
        row_count=len(df),
        column_count=len(df.columns),
    )

    db.add(new_dataset)
    db.commit()
    db.refresh(new_dataset)

    dataset_info = {
        "id": new_dataset.id,
        "filename": new_dataset.filename,
        "rows": new_dataset.row_count,
        "columns": new_dataset.column_count,
        "uploaded_at": new_dataset.created_at,
    }
    return {"message": "file upload successfully", "dataset": dataset_info}


@router.get("/datasets/")
def list_datasets(db: Session = Depends(get_db)):
    # db.query(Dataset) builds a SELECT * FROM datasets query
    # .all() executes it and returns a list of Dataset objects
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
def get_dataset_summary(dataset_id: int, db: Session = Depends(get_db)):

    # .filter(Dataset.id == dataset_id) → WHERE id = dataset_id
    # .first() returns the first matching row, or None if not found
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()

    if not dataset:
        raise HTTPException(status_code=404, detail="dataset not found")

    df = pd.read_csv(str(dataset.file_path))

    return {
        "id": dataset.id,
        "filename": dataset.filename,
        "rows": len(df),
        "columns": len(df.columns),
        "column_name": list(df.columns),
        "missing_values": df.isnull().sum().to_dict(),
        "data_types": {col: str(dtype) for col, dtype in df.dtypes.items()},
    }
