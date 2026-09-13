from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Dataset(Base):
    __tablename__ = "datasets"
    id = Column(Integer, primary_key=True, index=True)
    # Who uploaded it (audit/display only) — NOT the access-control field.
    # Access is via workspace membership; see app/services/access_control.py.
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    filename = Column(String, nullable=False)
    # Set only for a Dataset row derived from one sheet of a multi-sheet
    # Excel upload (Day 16) — distinguishes sibling rows that would
    # otherwise share an identical filename. Null for CSV uploads.
    sheet_name = Column(String, nullable=True)
    file_path = Column(String, nullable=False)
    row_count = Column(Integer, nullable=False)
    column_count = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    owner = relationship("User", back_populates="datasets")
    workspace = relationship("Workspace", back_populates="datasets")
