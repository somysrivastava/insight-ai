from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class SavedJoin(Base):
    """
    A reusable join definition (Day 17). `datasets` and `joins` mirror the
    request schema exactly (app/schemas/join.py) — stored as JSONB rather
    than normalized across several tables, since the spec is always read
    and written as one atomic document, never queried by its individual
    fields. This means dataset ids inside the JSON have no DB-level FK
    integrity; access_control.py re-validates every referenced dataset
    against the current workspace membership at execution time, every
    time, regardless — see app/services/join_service.py.
    """

    __tablename__ = "saved_joins"
    __table_args__ = (
        UniqueConstraint("workspace_id", "name", name="uq_saved_join_workspace_name"),
    )

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    datasets = Column(JSONB, nullable=False)
    joins = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    workspace = relationship("Workspace")
    user = relationship("User")
