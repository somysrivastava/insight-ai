from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class ExportJob(Base):
    """
    A completed (or failed) export attempt (Day 18). Written once by the
    Celery task when it finishes — not eagerly at submission — since
    GET /jobs/{task_id} already covers "is it ready" polling (Day 15);
    this table exists so the resulting file stays downloadable for
    longer (24h) than a Celery/Redis result does (1h, see
    app/worker.py's result_expires).

    `params` mirrors the request that produced this export (source
    type, question/group_by, etc.) as JSONB — same reasoning as Day
    17's SavedJoin: read/written as one atomic document, never queried
    by its individual fields.
    """

    __tablename__ = "export_jobs"

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    source_type = Column(String, nullable=False)  # "dataset_query" | "dataset_analytics" | "join_query" | "report"
    source_id = Column(Integer, nullable=False)  # dataset_id or join_id, depending on source_type
    params = Column(JSONB, nullable=False)
    format = Column(String, nullable=False)  # "csv" | "xlsx" | "pdf"
    status = Column(String, nullable=False)  # "success" | "failed"
    file_path = Column(String, nullable=True)  # set on success
    error = Column(String, nullable=True)  # set on failure
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    workspace = relationship("Workspace")
    user = relationship("User")
