from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class WorkspaceMember(Base):
    __tablename__ = "workspace_members"
    __table_args__ = (
        UniqueConstraint("user_id", "workspace_id", name="uq_workspace_member"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    role = Column(String, nullable=False, default="member")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="workspace_memberships")
    workspace = relationship("Workspace", back_populates="members")
