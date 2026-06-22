from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

# from pandas._libs.lib import i8max
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Dataset, User
from app.services.auth_service import get_current_user
from app.services.cleaning_service import clean_dataset, generate_quality_report

router = APIRouter(
    prefix="/datasets",
    tags=["Cleaning"],
)


class CleaningBase(BaseModel):
    remove_duplicates: Optional[bool] = True
    fill_missing_numeric: Optional[str] = "median"
    fill_missing_categorical: Optional[str] = "unknown"
    strip_whitespace: Optional[bool] = True
    normalise_column_names: Optional[bool] = True


@router.get("/{dataset_id}/quality")
def quality_report(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    print(f"DEBUG dataset.user_id={dataset.user_id!r} type={type(dataset.user_id)}")
    print(f"DEBUG current_user.id={current_user.id!r} type={type(current_user.id)}")
    if dataset.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    try:
        report = generate_quality_report(dataset.file_path)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error analysing document: {str(e)}"
        )
    return {
        "dataset_id": dataset_id,
        "dataset_name": dataset.filename,
        **report,
    }


@router.post("/{dataset_id}/clean")
def clean_dataset_endpoint(
    dataset_id: int,
    options: CleaningBase = CleaningBase(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    print(f"DEBUG dataset.user_id={dataset.user_id!r} type={type(dataset.user_id)}")
    print(f"DEBUG current_user.id={current_user.id!r} type={type(current_user.id)}")
    if dataset.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
    try:
        result = clean_dataset(dataset.file_path, options.model_dump())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error cleaning dataset: {str(e)}")
    return {
        "dataset_id": dataset_id,
        "dataset_name": dataset.filename,
        **result,
    }
