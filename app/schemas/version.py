from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class DatasetVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dataset_id: int
    version_number: int
    row_count: int
    column_count: int
    uploaded_by: int
    is_current: bool
    change_summary: Optional[str]
    created_at: datetime
