from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Dashboard(Base):
    """
    A named collection of pinned results (Day 21) — DashboardPin rows
    hold the actual query/result data; this row is just the container
    and its metadata. `is_active` (not in the original field list)
    mirrors AlertRule's field of the same name and purpose (Day 20):
    excluding a dashboard from daily_dashboard_refresh_task without
    deleting it. `is_default` is a plain flag with no enforced
    uniqueness — nothing reads it yet (no GET /dashboards/default),
    that's for a future consumer (the Day 26 frontend) to decide.
    """

    __tablename__ = "dashboards"

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    is_default = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    workspace = relationship("Workspace")
    user = relationship("User")
    pins = relationship(
        "DashboardPin",
        back_populates="dashboard",
        cascade="all, delete-orphan",
        order_by="DashboardPin.position",
    )
