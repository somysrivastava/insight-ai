from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class DatasetVersion(Base):
    """
    One historical snapshot of a Dataset's file (Day 23). Exactly one
    row per (dataset_id) has is_current=True at any time — that row's
    file_path/row_count/column_count are mirrored onto the parent
    Dataset (denormalized for every existing service that reads
    Dataset.file_path directly, unchanged since Day 5). version_number
    only ever increases, including on rollback (a rollback creates a
    new version whose content copies an old one, rather than rewinding
    the pointer) — see ADR-018.
    """

    __tablename__ = "dataset_versions"
    __table_args__ = (
        UniqueConstraint("dataset_id", "version_number", name="uq_dataset_version_number"),
    )

    id = Column(Integer, primary_key=True, index=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id"), nullable=False)
    version_number = Column(Integer, nullable=False)
    file_path = Column(String, nullable=False)
    row_count = Column(Integer, nullable=False)
    column_count = Column(Integer, nullable=False)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_current = Column(Boolean, nullable=False, default=False)
    change_summary = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    dataset = relationship("Dataset", back_populates="versions")
    uploader = relationship("User")
