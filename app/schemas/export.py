from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


class DatasetExportRequest(BaseModel):
    source: Literal["query", "insights", "trends", "breakdown"]
    format: Literal["csv", "xlsx", "pdf"]
    question: Optional[str] = Field(default=None, min_length=1, max_length=1000)
    group_by: Optional[str] = None

    @model_validator(mode="after")
    def _check_source_params(self) -> "DatasetExportRequest":
        if self.source == "query" and not self.question:
            raise ValueError("'question' is required when source is 'query'.")
        if self.source == "breakdown" and not self.group_by:
            raise ValueError("'group_by' is required when source is 'breakdown'.")
        return self


class JoinExportRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    format: Literal["csv", "xlsx", "pdf"]


class ReportExportRequest(BaseModel):
    format: Literal["csv", "xlsx", "pdf"]
