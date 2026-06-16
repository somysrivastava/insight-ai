import os
import shutil

import pandas as pd
from fastapi import APIRouter, File, UploadFile

router = APIRouter()

DATASETS = []

UPLOAD_FOLDER = "app/uploads"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@router.post("/upload")
async def upload_dataset(file: UploadFile = File(...)):
    file_path = f"{UPLOAD_FOLDER}/{file.filename}"

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    dataset_info = {
        "filename": file.filename,
        "content_type": file.content_type,
        "path": file_path,
    }

    DATASETS.append(dataset_info)
    #
    return {"message": "file upload successfully", "dataset": dataset_info}


@router.get("/datasets/{dataset_id}/summary")
def get_dataset_summary(dataset_id: int):
    if dataset_id < 0 or dataset_id >= len(DATASETS):
        return {"error": "dataset not found"}
    dataset = DATASETS[dataset_id]
    df = pd.read_csv(dataset["path"])
    rows = len(df)
    columns = len(df.columns)
    column_names = list(df.columns)
    return {"rows": rows,
        "columns": columns,
        "column_names": column_names, 
        "missing_values": df.isnull().sum().to_dict(),
        "data_types": df.dtypes.astype(str).to_dict()}
