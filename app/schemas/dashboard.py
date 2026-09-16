from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

PinType = Literal["dataset_query", "join_query", "analytics", "report"]


class DashboardCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    is_default: bool = False
    workspace_id: Optional[int] = None


class DashboardUpdateRequest(BaseModel):
    """All fields optional — PATCH semantics."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None


class DashboardPinCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    pin_type: PinType
    source_id: int
    query_params: dict[str, Any] = Field(default_factory=dict)


class DashboardPinUpdateRequest(BaseModel):
    """Title/position only — re-pin (delete + add) to change what a pin queries."""

    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    position: Optional[int] = None


class DashboardPinResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dashboard_id: int
    pinned_by: int
    title: str
    pin_type: str
    source_id: int
    query_params: dict[str, Any]
    last_refreshed_at: Optional[datetime]
    cached_result: Optional[dict[str, Any]]
    position: int
    created_at: datetime


class DashboardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    created_by: int
    name: str
    description: Optional[str]
    is_default: bool
    is_active: bool
    created_at: datetime


class DashboardDetailResponse(DashboardResponse):
    """GET /dashboards/{id} — the list endpoint returns DashboardResponse (no pins)."""

    pins: list[DashboardPinResponse] = []
