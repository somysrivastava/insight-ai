from typing import Any, Optional

from pydantic import BaseModel


class JobSubmitResponse(BaseModel):
    task_id: str
    status: str = "pending"


class JobResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
