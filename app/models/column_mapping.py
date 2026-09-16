from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class ColumnMapping(Base):
    """
    Human-readable metadata for one column of one dataset (Day 22) —
    display_name/description/unit feed ai_service.py's dataset context
    so the model understands a cryptically-named column like "del_t" as
    "Delivery Time (minutes)". The real column_name always stays what
    the model must output to run a query (execute_structured_query
    validates against real DataFrame columns, not display names) — this
    table is enrichment, never a substitute for the raw name. See
    ADR-017.
    """

    __tablename__ = "column_mappings"
    __table_args__ = (
        UniqueConstraint("dataset_id", "column_name", name="uq_column_mapping_dataset_column"),
    )

    id = Column(Integer, primary_key=True, index=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id"), nullable=False)
    column_name = Column(String, nullable=False)

    display_name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    unit = Column(String, nullable=True)
    is_metric = Column(Boolean, nullable=False, default=False)
    is_dimension = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    dataset = relationship("Dataset")
