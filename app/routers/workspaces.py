from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from app.schemas.workspace import WorkspaceResponse
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/workspaces", tags=["Workspaces"])


@router.get("/", response_model=list[WorkspaceResponse])
def list_workspaces(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Lists workspaces the current user belongs to. Every user has at
    least their auto-provisioned personal workspace (Day 16); creating
    additional workspaces and inviting members is deliberately deferred
    to a later day — see docs/ADR.md ADR-011.
    """
    rows = (
        db.query(Workspace, WorkspaceMember.role)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .filter(WorkspaceMember.user_id == current_user.id)
        .all()
    )
    return [
        WorkspaceResponse(
            id=workspace.id,
            name=workspace.name,
            org_id=workspace.org_id,
            role=role,
            created_at=workspace.created_at,
        )
        for workspace, role in rows
    ]
