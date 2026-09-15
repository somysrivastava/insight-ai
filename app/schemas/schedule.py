from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, model_validator


class ScheduledReportCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    source_type: Literal["dataset_query", "join_query", "report"]
    source_id: int
    question: Optional[str] = Field(default=None, min_length=1, max_length=1000)
    export_format: Literal["csv", "xlsx", "pdf"]

    frequency: Literal["daily", "weekly", "monthly"]
    day_of_week: Optional[int] = Field(default=None, ge=0, le=6)
    day_of_month: Optional[int] = Field(default=None, ge=1, le=31)
    hour: int = Field(..., ge=0, le=23)

    recipients: list[EmailStr] = Field(..., min_length=1)

    @model_validator(mode="after")
    def _check_fields(self) -> "ScheduledReportCreateRequest":
        if self.source_type in ("dataset_query", "join_query") and not self.question:
            raise ValueError("'question' is required when source_type is 'dataset_query' or 'join_query'.")
        if self.source_type == "report" and self.question:
            raise ValueError("'question' is not used when source_type is 'report'.")

        if self.frequency == "weekly" and self.day_of_week is None:
            raise ValueError("'day_of_week' is required when frequency is 'weekly'.")
        if self.frequency != "weekly" and self.day_of_week is not None:
            raise ValueError("'day_of_week' is only used when frequency is 'weekly'.")

        if self.frequency == "monthly" and self.day_of_month is None:
            raise ValueError("'day_of_month' is required when frequency is 'monthly'.")
        if self.frequency != "monthly" and self.day_of_month is not None:
            raise ValueError("'day_of_month' is only used when frequency is 'monthly'.")

        return self


class ScheduledReportUpdateRequest(BaseModel):
    """All fields optional — PATCH semantics. What identifies the
    schedule (source_type/source_id/workspace) is not patchable; delete
    and recreate for that."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    question: Optional[str] = Field(default=None, min_length=1, max_length=1000)
    export_format: Optional[Literal["csv", "xlsx", "pdf"]] = None

    frequency: Optional[Literal["daily", "weekly", "monthly"]] = None
    day_of_week: Optional[int] = Field(default=None, ge=0, le=6)
    day_of_month: Optional[int] = Field(default=None, ge=1, le=31)
    hour: Optional[int] = Field(default=None, ge=0, le=23)

    recipients: Optional[list[EmailStr]] = Field(default=None, min_length=1)
    is_active: Optional[bool] = None


class ScheduledReportResponse(BaseModel):
    id: int
    workspace_id: int
    name: str
    source_type: str
    source_id: int
    question: Optional[str]
    export_format: str
    frequency: str
    day_of_week: Optional[int]
    day_of_month: Optional[int]
    hour: int
    recipients: list[str]
    is_active: bool
    last_run_at: Optional[datetime]
    next_run_at: datetime
    created_at: datetime
