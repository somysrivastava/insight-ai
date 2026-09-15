from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class ScheduledReport(Base):
    """
    A recurring export (Day 19) — a narrower version of Day 18's export
    scope: only dataset_query / join_query / report, not a bare
    insights/trends/breakdown export. `next_run_at` is the single field
    that drives everything: app/tasks/scheduled_tasks.py's poller finds
    due rows by it and atomically claims them (see ADR-014) before doing
    any work, to avoid double-sending if an export runs long.
    """

    __tablename__ = "scheduled_reports"

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)

    source_type = Column(String, nullable=False)  # "dataset_query" | "join_query" | "report"
    source_id = Column(Integer, nullable=False)  # dataset_id or join_id, depending on source_type
    question = Column(String, nullable=True)  # required for dataset_query / join_query, null for report
    export_format = Column(String, nullable=False)  # "csv" | "xlsx" | "pdf"

    frequency = Column(String, nullable=False)  # "daily" | "weekly" | "monthly"
    day_of_week = Column(Integer, nullable=True)  # 0-6, Monday=0 — weekly only
    day_of_month = Column(Integer, nullable=True)  # 1-31, clamped to the real last day — monthly only
    hour = Column(Integer, nullable=False)  # 0-23 UTC

    recipients = Column(JSONB, nullable=False)  # list[str] email addresses

    is_active = Column(Boolean, nullable=False, default=True)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    next_run_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    workspace = relationship("Workspace")
    user = relationship("User")
