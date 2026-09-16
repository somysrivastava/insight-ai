from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class DashboardPin(Base):
    """
    One pinned result on a Dashboard (Day 21). `pin_type` + `source_id` +
    `query_params` together describe how to re-run the underlying query
    — see app/services/dashboard_service.py's `_execute_pin` for the
    exact mapping (dataset_query/analytics/report resolve `source_id` as
    a dataset id; join_query resolves it as an existing SavedJoin id).
    `cached_result` holds the last computed output; a plain GET never
    recomputes it, only POST .../refresh does. A failed refresh
    overwrites `cached_result` with `{"error": "..."}` rather than
    leaving stale data silently in place — see ADR-016.
    """

    __tablename__ = "dashboard_pins"

    id = Column(Integer, primary_key=True, index=True)
    dashboard_id = Column(Integer, ForeignKey("dashboards.id"), nullable=False)
    pinned_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)

    pin_type = Column(String, nullable=False)  # "dataset_query" | "join_query" | "analytics" | "report"
    source_id = Column(Integer, nullable=False)  # a dataset id, or a SavedJoin id for "join_query"
    query_params = Column(JSONB, nullable=False, default=dict)

    last_refreshed_at = Column(DateTime(timezone=True), nullable=True)
    cached_result = Column(JSONB, nullable=True)

    position = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    dashboard = relationship("Dashboard", back_populates="pins")
    user = relationship("User")
