from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ColumnMappingUpsert(BaseModel):
    """One item in a bulk PUT — display_name is required, same as a brand-new mapping needs."""

    column_name: str = Field(..., min_length=1)
    display_name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    unit: Optional[str] = None
    is_metric: bool = False
    is_dimension: bool = False


class DictionaryBulkUpsertRequest(BaseModel):
    mappings: list[ColumnMappingUpsert] = Field(..., min_length=1)


class ColumnMappingPatchRequest(BaseModel):
    """All fields optional — PATCH semantics. Only ever applied to an already-existing mapping."""

    display_name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    unit: Optional[str] = None
    is_metric: Optional[bool] = None
    is_dimension: Optional[bool] = None


class ColumnMappingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dataset_id: int
    column_name: str
    display_name: str
    description: Optional[str]
    unit: Optional[str]
    is_metric: bool
    is_dimension: bool
    created_at: datetime
    updated_at: Optional[datetime]


class DictionarySuggestResponse(BaseModel):
    suggested: list[ColumnMappingResponse]
    skipped_existing: list[str]
