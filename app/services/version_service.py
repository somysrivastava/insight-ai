# WHY THIS FILE EXISTS:
# Owns DatasetVersion CRUD and the mechanics of advancing a Dataset to
# a new version — storage, row/column bookkeeping, the is_current flip,
# and the column-structure guard that keeps every version in a
# dataset's history sharing one column set (so alert rules, dashboard
# pins, and column mappings — all keyed by column name — never
# silently break under a version push). Deliberately doesn't touch
# Celery or the alert/dashboard-refresh triggers itself — those are
# fired by the router (app/routers/versions.py), the same layering
# dataset.py's own /upload endpoint already uses.

import io
from pathlib import Path
from typing import Optional

import pandas as pd
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.dataset import Dataset
from app.models.dataset_version import DatasetVersion
from app.services.storage_service import get_storage_backend, load_dataframe


def get_versions(db: Session, dataset_id: int) -> list[DatasetVersion]:
    return (
        db.query(DatasetVersion)
        .filter(DatasetVersion.dataset_id == dataset_id)
        .order_by(DatasetVersion.version_number.desc())
        .all()
    )


def get_version(db: Session, dataset_id: int, version_number: int) -> Optional[DatasetVersion]:
    return (
        db.query(DatasetVersion)
        .filter(DatasetVersion.dataset_id == dataset_id, DatasetVersion.version_number == version_number)
        .first()
    )


def create_initial_version(db: Session, dataset: Dataset, user_id: int) -> DatasetVersion:
    """
    Version 1 for a brand-new dataset, called right after dataset.py's
    /upload endpoint creates the Dataset row — reuses the file already
    saved under Dataset.file_path (no duplicate save). Mirrors what the
    Day 23 backfill migration did for every pre-existing dataset.
    """
    version = DatasetVersion(
        dataset_id=dataset.id,
        version_number=1,
        file_path=dataset.file_path,
        row_count=dataset.row_count,
        column_count=dataset.column_count,
        uploaded_by=user_id,
        is_current=True,
        change_summary=None,
    )
    db.add(version)
    dataset.current_version_number = 1
    db.commit()
    db.refresh(version)
    return version


def _parse_dataframe(file_bytes: bytes, filename: str) -> pd.DataFrame:
    suffix = Path(filename).suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(io.BytesIO(file_bytes))
    if suffix in (".xlsx", ".xls"):
        sheets = pd.read_excel(io.BytesIO(file_bytes), sheet_name=None)
        if len(sheets) != 1:
            raise ValueError(
                "Multi-sheet Excel files aren't supported for versioning — each dataset "
                "version is one sheet's lineage. Use POST /upload for a new multi-sheet "
                "dataset instead."
            )
        return next(iter(sheets.values()))
    raise ValueError(f"Unsupported file type: {suffix}")


def _validate_column_structure(current_columns: list[str], new_columns: list[str]) -> None:
    current_set, new_set = set(current_columns), set(new_columns)
    added = new_set - current_set
    removed = current_set - new_set
    if added or removed:
        parts = []
        if added:
            parts.append(f"added: {sorted(added)}")
        if removed:
            parts.append(f"removed: {sorted(removed)}")
        raise ValueError(
            "New version's columns don't match the current version — " + "; ".join(parts) + ". "
            "Column structure must stay identical across versions so existing alert "
            "rules, dashboard pins, and column mappings keep working."
        )


def _next_version_number(db: Session, dataset_id: int) -> int:
    current_max = (
        db.query(DatasetVersion.version_number)
        .filter(DatasetVersion.dataset_id == dataset_id)
        .order_by(DatasetVersion.version_number.desc())
        .first()
    )
    return (current_max[0] + 1) if current_max else 1


def _advance_to_new_version(
    db: Session,
    dataset: Dataset,
    version_number: int,
    storage_key: str,
    row_count: int,
    column_count: int,
    uploaded_by: int,
    change_summary: Optional[str],
) -> DatasetVersion:
    """
    Shared tail of push_new_version and rollback_version: flips the old
    current version off, inserts the new one, and mirrors its
    file_path/row_count/column_count onto the Dataset row — one commit,
    so a crash mid-way never leaves Dataset and DatasetVersion
    disagreeing about which version is current.
    """
    db.query(DatasetVersion).filter(
        DatasetVersion.dataset_id == dataset.id, DatasetVersion.is_current.is_(True)
    ).update({"is_current": False})

    version = DatasetVersion(
        dataset_id=dataset.id,
        version_number=version_number,
        file_path=storage_key,
        row_count=row_count,
        column_count=column_count,
        uploaded_by=uploaded_by,
        is_current=True,
        change_summary=change_summary,
    )
    db.add(version)

    dataset.file_path = storage_key
    dataset.row_count = row_count
    dataset.column_count = column_count
    dataset.current_version_number = version_number

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValueError("A version push is already in progress for this dataset — try again.")
    db.refresh(version)
    return version


def push_new_version(
    db: Session,
    dataset: Dataset,
    file_bytes: bytes,
    filename: str,
    user_id: int,
    change_summary: Optional[str],
) -> DatasetVersion:
    """
    Validates the new file's columns exactly match the current
    version's, saves it under a version-specific storage key (never
    overwriting an older version's file — GET .../{n}/download has to
    keep working for every past version), then advances the dataset.
    """
    new_df = _parse_dataframe(file_bytes, filename)
    current_df = load_dataframe(dataset.file_path)
    _validate_column_structure(list(current_df.columns), list(new_df.columns))

    version_number = _next_version_number(db, dataset.id)
    storage_key = f"{dataset.workspace_id}/{dataset.id}/v{version_number}_{filename}"
    get_storage_backend().save(file_bytes, storage_key)

    return _advance_to_new_version(
        db, dataset, version_number, storage_key, len(new_df), len(new_df.columns), user_id, change_summary
    )


def rollback_version(db: Session, dataset: Dataset, target: DatasetVersion, user_id: int) -> DatasetVersion:
    """
    Creates a NEW version whose content copies `target`'s — version
    numbers only ever go up, including through a rollback, so there's
    no special-casing for what the next real push after this gets
    numbered, and the rollback itself is a visible, permanent event in
    the history rather than a rewind. No column-structure re-validation
    needed: every version already shares one column set by construction
    (each push was validated against its own predecessor). Reuses
    target's existing storage key rather than duplicating the file.
    """
    version_number = _next_version_number(db, dataset.id)
    change_summary = f"Rolled back to version {target.version_number}"
    return _advance_to_new_version(
        db, dataset, version_number, target.file_path, target.row_count, target.column_count, user_id, change_summary
    )
