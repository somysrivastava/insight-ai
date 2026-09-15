from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field


class AlertRuleCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    dataset_id: int
    column: str = Field(..., min_length=1)
    metric: Literal["mean", "sum", "count", "max", "min"]

    condition: Literal["gt", "lt", "gte", "lte", "eq"]
    threshold: float

    use_statistical: bool = False
    z_score_threshold: float = 2.0

    frequency: Literal["on_upload", "daily", "both"]
    recipients: list[EmailStr] = Field(..., min_length=1)


class AlertRuleUpdateRequest(BaseModel):
    """All fields optional — PATCH semantics. dataset_id is not
    patchable; delete and recreate to watch a different dataset."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    column: Optional[str] = Field(default=None, min_length=1)
    metric: Optional[Literal["mean", "sum", "count", "max", "min"]] = None

    condition: Optional[Literal["gt", "lt", "gte", "lte", "eq"]] = None
    threshold: Optional[float] = None

    use_statistical: Optional[bool] = None
    z_score_threshold: Optional[float] = None

    frequency: Optional[Literal["on_upload", "daily", "both"]] = None
    recipients: Optional[list[EmailStr]] = Field(default=None, min_length=1)
    is_active: Optional[bool] = None


class AlertRuleResponse(BaseModel):
    id: int
    workspace_id: int
    name: str
    dataset_id: int
    column: str
    metric: str
    condition: str
    threshold: float
    use_statistical: bool
    z_score_threshold: float
    frequency: str
    recipients: list[str]
    is_active: bool
    last_checked_at: Optional[datetime]
    last_triggered_at: Optional[datetime]
    created_at: datetime


class AlertHistoryResponse(BaseModel):
    id: int
    alert_rule_id: int
    checked_at: datetime
    triggered: bool
    actual_value: float
    z_score: Optional[float]
    alert_type: str
    email_sent: bool
    error: Optional[str]
