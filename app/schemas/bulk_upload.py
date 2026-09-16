from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class BulkUploadJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    created_by: int
    status: str
    total_files: int
    succeeded: int
    failed: int
    results: list[dict[str, Any]]
    created_at: datetime
    completed_at: Optional[datetime]


class BulkUploadSubmitResponse(BaseModel):
    job_id: int
