from datetime import datetime

from pydantic import BaseModel


class WorkspaceResponse(BaseModel):
    id: int
    name: str
    org_id: int
    role: str
    created_at: datetime
