from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class BulkUploadJob(Base):
    """
    Tracks one bulk-upload request (Day 24) — up to 50 files, each
    processed independently by process_bulk_upload_task, one at a time,
    updating results/succeeded/failed incrementally so GET
    /bulk-upload/{id} shows real progress while status="processing".
    Counts at the expanded (per-dataset) level, not the raw-attachment
    level — a multi-sheet Excel contributes one results entry per
    sheet, so succeeded + failed always equals total_files exactly
    (your explicit choice; total_files may start lower and settle as
    each attachment is parsed). No record_job_owner/GET /jobs/{task_id}
    involvement — this is a first-class DB row with its own
    workspace-scoped access, same as ScheduledReport/AlertRule.
    """

    __tablename__ = "bulk_upload_jobs"

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)

    status = Column(String, nullable=False, default="pending")  # pending|processing|completed|partially_failed|failed
    total_files = Column(Integer, nullable=False, default=0)
    succeeded = Column(Integer, nullable=False, default=0)
    failed = Column(Integer, nullable=False, default=0)
    results = Column(JSONB, nullable=False, default=list)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    workspace = relationship("Workspace")
    user = relationship("User")
