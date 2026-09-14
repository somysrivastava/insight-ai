from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class JoinDatasetRef(BaseModel):
    id: int
    alias: str = Field(..., min_length=1, max_length=100)


class JoinColumnPair(BaseModel):
    left: str
    right: str


class JoinStep(BaseModel):
    left_alias: str
    right_alias: str
    on: list[JoinColumnPair] = Field(..., min_length=1)
    type: Literal["left", "inner", "right"] = "left"


class JoinDefinition(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    datasets: list[JoinDatasetRef] = Field(..., min_length=2)
    joins: list[JoinStep] = Field(..., min_length=1)


class JoinQueryRequest(JoinDefinition):
    question: str = Field(..., min_length=1, max_length=1000)


class SavedJoinQueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)


class JoinQueryResponse(BaseModel):
    answer: str
    data: dict[str, Any]
    query_used: dict[str, Any]
    tokens_used: int
    join_id: Optional[int] = None


class SavedJoinResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    workspace_id: int
    datasets: list[JoinDatasetRef]
    joins: list[JoinStep]
    created_at: datetime
