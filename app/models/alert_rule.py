from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class AlertRule(Base):
    """
    Monitors one column of one dataset (Day 20). Two independent checks
    can fire per evaluation: threshold (always) and statistical
    (additionally, if use_statistical) — each gets its own AlertHistory
    row and its own email. See ADR-015.
    """

    __tablename__ = "alert_rules"

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)

    dataset_id = Column(Integer, ForeignKey("datasets.id"), nullable=False)
    column = Column(String, nullable=False)  # which column of the dataset to watch
    metric = Column(String, nullable=False)  # "mean" | "sum" | "count" | "max" | "min"

    condition = Column(String, nullable=False)  # "gt" | "lt" | "gte" | "lte" | "eq"
    threshold = Column(Float, nullable=False)

    use_statistical = Column(Boolean, nullable=False, default=False)
    z_score_threshold = Column(Float, nullable=False, default=2.0)

    frequency = Column(String, nullable=False)  # "on_upload" | "daily" | "both"
    recipients = Column(JSONB, nullable=False)  # list[str] email addresses

    is_active = Column(Boolean, nullable=False, default=True)
    last_checked_at = Column(DateTime(timezone=True), nullable=True)
    last_triggered_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    workspace = relationship("Workspace")
    user = relationship("User")
    dataset = relationship("Dataset")
    history = relationship("AlertHistory", back_populates="alert_rule", cascade="all, delete-orphan")
