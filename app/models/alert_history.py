from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class AlertHistory(Base):
    """
    One row per *evaluation* of one check (threshold or statistical),
    not just per trigger — broadened from a literal "triggered events
    only" table (Day 20 spec's `triggered_at` naming) because the
    statistical check's rolling-window baseline needs a representative
    sample of past values, not just past anomalies. z-scoring today's
    value against the mean of *only prior triggers* would be
    statistically meaningless — a biased sample of extremes, not a
    normal baseline. See ADR-015.
    """

    __tablename__ = "alert_history"

    id = Column(Integer, primary_key=True, index=True)
    alert_rule_id = Column(Integer, ForeignKey("alert_rules.id"), nullable=False)
    checked_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    triggered = Column(Boolean, nullable=False)
    actual_value = Column(Float, nullable=False)
    z_score = Column(Float, nullable=True)  # only set for alert_type="statistical"
    alert_type = Column(String, nullable=False)  # "threshold" | "statistical"
    email_sent = Column(Boolean, nullable=False, default=False)
    error = Column(String, nullable=True)  # set if email sending failed

    alert_rule = relationship("AlertRule", back_populates="history")
