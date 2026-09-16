import io
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from app.models.dataset import Dataset
from app.services import version_service
from app.services.storage_service import get_storage_backend, get_storage_key


def generate_summary(file_path: str):
    df = pd.read_csv(file_path)
    return {
        "rows": len(df),
        "columns": len(df.columns),
        "column_names": list(df.columns),
    }


def _sanitize_for_key(name: str) -> str:
    """Keeps sheet/file names from introducing path separators into a storage key."""
    return name.strip().replace("/", "_").replace("\\", "_")


def create_datasets_from_file(
    db: Session, file_bytes: bytes, filename: str, workspace_id: int, user_id: int
) -> list[Dataset]:
    """
    Turns one uploaded file into one or more Dataset rows (+ each one's
    initial DatasetVersion, Day 23) — a plain CSV becomes one row, a
    multi-sheet Excel becomes one row per sheet, each independently
    queryable, exactly like the original /upload endpoint always
    behaved. Extracted here (Day 24) so both that endpoint and the bulk
    upload task (app/tasks/bulk_tasks.py) share one implementation
    instead of two copies drifting apart. Framework-agnostic — raises
    ValueError for bad file content, not HTTPException, same pattern as
    access_control.py, so a Celery task with no HTTP context can call
    it directly.
    """
    if filename.lower().endswith((".xlsx", ".xls")):
        try:
            sheets = pd.read_excel(io.BytesIO(file_bytes), sheet_name=None)
        except Exception as e:
            raise ValueError(f"Invalid Excel file: {str(e)}")

        if not sheets:
            raise ValueError("Excel file has no sheets.")

        base_name = Path(filename).stem
        backend = get_storage_backend()
        created = []

        for sheet_name, df in sheets.items():
            storage_key = get_storage_key(
                workspace_id, f"{_sanitize_for_key(base_name)}__{_sanitize_for_key(sheet_name)}.csv"
            )
            backend.save(df.to_csv(index=False).encode("utf-8"), storage_key)

            new_dataset = Dataset(
                user_id=user_id,
                workspace_id=workspace_id,
                filename=filename,
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
            version_service.create_initial_version(db, d, user_id)
        return created

    storage_key = get_storage_key(workspace_id, filename)
    get_storage_backend().save(file_bytes, storage_key)

    try:
        df = pd.read_csv(io.BytesIO(file_bytes))
    except Exception as e:
        raise ValueError(f"Invalid CSV file: {str(e)}")

    new_dataset = Dataset(
        user_id=user_id,
        workspace_id=workspace_id,
        filename=filename,
        file_path=storage_key,
        row_count=len(df),
        column_count=len(df.columns),
    )
    db.add(new_dataset)
    db.commit()
    db.refresh(new_dataset)
    version_service.create_initial_version(db, new_dataset, user_id)
    return [new_dataset]
