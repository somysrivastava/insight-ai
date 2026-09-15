# WHY THIS FILE EXISTS:
# Every service that touches a dataset (analytics, cleaning, reports,
# visualization) needs to turn "a Dataset row" into "a DataFrame" without
# caring whether the underlying bytes live on local disk or in S3.
# Before this file existed, each service reimplemented that step itself
# assuming local disk, which is exactly what broke when Day 12 moved
# uploads to S3 without touching the other four call sites.
#
# StorageBackend is the abstraction those services now depend on instead
# of a concrete storage mechanism (Dependency Inversion). Swapping the
# active backend is a one-line env var change, not a five-file hunt.

import io
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

import pandas as pd

from app.services import s3_service


class StorageBackend(ABC):
    @abstractmethod
    def save(self, file_bytes: bytes, key: str) -> str:
        """Persist bytes under `key`, returning the key to store on the Dataset row."""

    @abstractmethod
    def load(self, key: str) -> bytes:
        """Return the raw bytes stored under `key`."""

    @abstractmethod
    def url_for(self, key: str, expires_in: int = 3600) -> Optional[str]:
        """Return a direct download URL for `key`, or None if the backend has no such concept."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Remove whatever is stored under `key`. No-op if it doesn't exist."""


class LocalStorageBackend(StorageBackend):
    def __init__(self, root: str = "app/uploads"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        return self.root / key

    def save(self, file_bytes: bytes, key: str) -> str:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(file_bytes)
        return key

    def load(self, key: str) -> bytes:
        path = self._resolve(key)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {key}")
        return path.read_bytes()

    def url_for(self, key: str, expires_in: int = 3600) -> Optional[str]:
        return None

    def delete(self, key: str) -> None:
        self._resolve(key).unlink(missing_ok=True)


class S3StorageBackend(StorageBackend):
    """Thin adapter over s3_service.py — kept in the codebase but inactive
    unless STORAGE_BACKEND=s3 is set. See ADR-004."""

    def __init__(self, prefix: str = ""):
        self.prefix = prefix

    def _key(self, key: str) -> str:
        return f"{self.prefix}/{key}" if self.prefix else key

    def save(self, file_bytes: bytes, key: str) -> str:
        return s3_service.upload_file_to_s3(file_bytes, self._key(key))

    def load(self, key: str) -> bytes:
        return s3_service.download_file_from_s3(self._key(key))

    def url_for(self, key: str, expires_in: int = 3600) -> Optional[str]:
        return s3_service.generate_presigned_url(self._key(key), expires_in)

    def delete(self, key: str) -> None:
        s3_service.delete_file_from_s3(self._key(key))


def get_storage_backend(purpose: str = "uploads") -> StorageBackend:
    """
    `purpose` picks which local directory / S3 key prefix this backend
    reads and writes under — e.g. "uploads" (default, dataset files) vs
    "exports" (Day 18, generated CSV/Excel/PDF files). Swapping the
    active backend, or adding a new purpose, is a change here, not in
    every caller.
    """
    backend = os.getenv("STORAGE_BACKEND", "local").lower()
    if backend == "s3":
        return S3StorageBackend(prefix=purpose)
    return LocalStorageBackend(root=f"app/{purpose}")


def get_storage_key(scope_id, filename: str) -> str:
    """
    `scope_id` groups stored files by sharing boundary. Since Day 16,
    that's a workspace_id (everyone in a workspace can access its
    files) — earlier callers passed a user_id; either works identically
    here, this function just joins whatever id it's given with the
    filename.
    """
    return f"{scope_id}/{filename}"


def load_dataframe(file_path: str, backend: Optional[StorageBackend] = None) -> pd.DataFrame:
    """Canonical Dataset-row -> DataFrame loader. Use this instead of
    calling pd.read_csv/read_excel directly on dataset.file_path."""
    backend = backend or get_storage_backend()
    file_bytes = backend.load(file_path)
    suffix = Path(file_path).suffix.lower()

    if suffix == ".csv":
        return pd.read_csv(io.BytesIO(file_bytes))
    elif suffix in (".xlsx", ".xls"):
        return pd.read_excel(io.BytesIO(file_bytes))
    raise ValueError(f"Unsupported file type: {suffix}")


def save_dataframe(df: pd.DataFrame, file_path: str, backend: Optional[StorageBackend] = None) -> None:
    """Counterpart to load_dataframe, for services (e.g. cleaning) that
    write a modified DataFrame back to storage."""
    backend = backend or get_storage_backend()
    suffix = Path(file_path).suffix.lower()
    buf = io.BytesIO()

    if suffix == ".csv":
        df.to_csv(buf, index=False)
    elif suffix in (".xlsx", ".xls"):
        df.to_excel(buf, index=False)
    else:
        raise ValueError(f"Unsupported file type: {suffix}")

    backend.save(buf.getvalue(), file_path)
