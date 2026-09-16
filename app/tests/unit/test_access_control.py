import pytest
from fastapi import HTTPException

from app.services.access_control import (
    check_workspace_membership,
    get_dataset_for_user,
    require_dataset_access,
    require_workspace_access,
    require_workspace_membership,
    resolve_workspace_id,
)
from app.tests.conftest import create_owned_dataset, create_user


class TestGetDatasetForUser:
    def test_success_for_a_member(self, db):
        dataset = create_owned_dataset(db)
        result = get_dataset_for_user(db, dataset.id, dataset.user_id)
        assert result.id == dataset.id

    def test_raises_value_error_for_unknown_dataset(self, db):
        with pytest.raises(ValueError, match="not found"):
            get_dataset_for_user(db, 999999, 1)

    def test_raises_permission_error_for_non_member(self, db):
        dataset = create_owned_dataset(db)
        outsider = create_user(db)
        with pytest.raises(PermissionError, match="Access denied"):
            get_dataset_for_user(db, dataset.id, outsider.id)


class TestRequireDatasetAccess:
    def test_success_returns_dataset(self, db):
        dataset = create_owned_dataset(db)
        assert require_dataset_access(db, dataset.id, dataset.user_id).id == dataset.id

    def test_unknown_dataset_is_404(self, db):
        with pytest.raises(HTTPException) as exc_info:
            require_dataset_access(db, 999999, 1)
        assert exc_info.value.status_code == 404

    def test_non_member_is_403(self, db):
        dataset = create_owned_dataset(db)
        outsider = create_user(db)
        with pytest.raises(HTTPException) as exc_info:
            require_dataset_access(db, dataset.id, outsider.id)
        assert exc_info.value.status_code == 403


class TestResolveWorkspaceId:
    def test_raises_value_error_when_user_has_no_workspace(self, db):
        user = create_user(db)  # no membership created for this user
        with pytest.raises(ValueError, match="don't belong to any workspace"):
            resolve_workspace_id(db, user.id)

    def test_defaults_to_first_membership_when_none_requested(self, db):
        dataset = create_owned_dataset(db)
        assert resolve_workspace_id(db, dataset.user_id) == dataset.workspace_id

    def test_explicit_workspace_id_honored_when_member(self, db):
        dataset = create_owned_dataset(db)
        assert resolve_workspace_id(db, dataset.user_id, dataset.workspace_id) == dataset.workspace_id

    def test_explicit_workspace_id_denied_when_not_a_member(self, db):
        dataset = create_owned_dataset(db)
        other_dataset = create_owned_dataset(db)
        with pytest.raises(PermissionError, match="Access denied"):
            resolve_workspace_id(db, dataset.user_id, other_dataset.workspace_id)


class TestRequireWorkspaceAccess:
    def test_success(self, db):
        dataset = create_owned_dataset(db)
        assert require_workspace_access(db, dataset.user_id) == dataset.workspace_id

    def test_no_workspace_is_404(self, db):
        user = create_user(db)
        with pytest.raises(HTTPException) as exc_info:
            require_workspace_access(db, user.id)
        assert exc_info.value.status_code == 404

    def test_denied_workspace_is_403(self, db):
        dataset = create_owned_dataset(db)
        other_dataset = create_owned_dataset(db)
        with pytest.raises(HTTPException) as exc_info:
            require_workspace_access(db, dataset.user_id, other_dataset.workspace_id)
        assert exc_info.value.status_code == 403


class TestWorkspaceMembership:
    def test_check_passes_for_member(self, db):
        dataset = create_owned_dataset(db)
        check_workspace_membership(db, dataset.workspace_id, dataset.user_id)  # no raise

    def test_check_raises_for_non_member(self, db):
        dataset = create_owned_dataset(db)
        outsider = create_user(db)
        with pytest.raises(PermissionError):
            check_workspace_membership(db, dataset.workspace_id, outsider.id)

    def test_require_wrapper_is_403_for_non_member(self, db):
        dataset = create_owned_dataset(db)
        outsider = create_user(db)
        with pytest.raises(HTTPException) as exc_info:
            require_workspace_membership(db, dataset.workspace_id, outsider.id)
        assert exc_info.value.status_code == 403
