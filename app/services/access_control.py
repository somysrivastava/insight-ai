# WHY THIS FILE EXISTS:
# Day 16 moves dataset access from direct ownership (dataset.user_id ==
# current_user.id) to workspace membership. Every router and Celery task
# that touches a dataset needs the same check, so it lives in exactly
# one place instead of being rewritten seven times with the same logic
# (and the same risk of one copy drifting from the rest — see
# ARCHITECTURE.md §4 on the duplicated ownership-check pattern this
# replaces).
#
# Framework-agnostic on purpose: raises plain ValueError/PermissionError
# rather than HTTPException, so both FastAPI routers (via the require_*
# wrappers below) and Celery tasks (which have no HTTP context) can use
# the same core checks.

from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Dataset
from app.models.workspace_member import WorkspaceMember


def get_dataset_for_user(db: Session, dataset_id: int, user_id: int) -> Dataset:
    """
    Loads a Dataset row and verifies the user has access via workspace
    membership. Raises ValueError if the dataset doesn't exist, or
    PermissionError if the user isn't a member of its workspace.
    """
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise ValueError(f"Dataset {dataset_id} not found.")

    has_access = (
        db.query(WorkspaceMember)
        .filter(
            WorkspaceMember.workspace_id == dataset.workspace_id,
            WorkspaceMember.user_id == user_id,
        )
        .first()
        is not None
    )
    if not has_access:
        raise PermissionError("Access denied.")

    return dataset


def require_dataset_access(db: Session, dataset_id: int, user_id: int) -> Dataset:
    """FastAPI-facing wrapper: same check, translated to HTTP status codes."""
    try:
        return get_dataset_for_user(db, dataset_id, user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


def resolve_workspace_id(db: Session, user_id: int, requested_workspace_id: Optional[int] = None) -> int:
    """
    Determines which workspace an action (e.g. upload) should target.

    If a workspace_id is explicitly requested, verifies membership and
    uses it. Otherwise defaults to the user's first workspace — the only
    real option today since every user has exactly one (their
    auto-provisioned personal workspace); becomes an actual choice once a
    user can belong to more than one (workspace creation/invites, a
    later day).
    """
    memberships = db.query(WorkspaceMember).filter(WorkspaceMember.user_id == user_id).all()
    if not memberships:
        raise ValueError("You don't belong to any workspace.")

    if requested_workspace_id is not None:
        if not any(m.workspace_id == requested_workspace_id for m in memberships):
            raise PermissionError("Access denied to the requested workspace.")
        return requested_workspace_id

    return memberships[0].workspace_id


def require_workspace_access(db: Session, user_id: int, requested_workspace_id: Optional[int] = None) -> int:
    """FastAPI-facing wrapper: same resolution, translated to HTTP status codes."""
    try:
        return resolve_workspace_id(db, user_id, requested_workspace_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


def check_workspace_membership(db: Session, workspace_id: int, user_id: int) -> None:
    """
    Verifies a user is a member of a specific workspace, independent of
    any dataset — needed for objects scoped to a workspace as a whole
    rather than to one dataset (e.g. a saved join's metadata, Day 17).
    Raises PermissionError if not a member.
    """
    is_member = (
        db.query(WorkspaceMember)
        .filter(WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.user_id == user_id)
        .first()
        is not None
    )
    if not is_member:
        raise PermissionError("Access denied.")


def require_workspace_membership(db: Session, workspace_id: int, user_id: int) -> None:
    """FastAPI-facing wrapper: same check, translated to HTTP status codes."""
    try:
        check_workspace_membership(db, workspace_id, user_id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
