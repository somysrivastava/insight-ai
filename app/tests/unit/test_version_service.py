import pytest

from app.models.dataset_version import DatasetVersion
from app.services.version_service import (
    _next_version_number,
    _validate_column_structure,
    create_initial_version,
)
from app.tests.conftest import create_owned_dataset


class TestValidateColumnStructure:
    def test_identical_columns_passes(self):
        _validate_column_structure(["region", "revenue"], ["region", "revenue"])  # no raise

    def test_different_order_still_passes(self):
        # Column structure is validated as a set, not a sequence — order
        # doesn't matter, only membership.
        _validate_column_structure(["region", "revenue"], ["revenue", "region"])  # no raise

    def test_added_column_raises(self):
        with pytest.raises(ValueError, match="added"):
            _validate_column_structure(["region", "revenue"], ["region", "revenue", "units"])

    def test_removed_column_raises(self):
        with pytest.raises(ValueError, match="removed"):
            _validate_column_structure(["region", "revenue", "units"], ["region", "revenue"])

    def test_both_added_and_removed_reported_together(self):
        with pytest.raises(ValueError) as exc_info:
            _validate_column_structure(["region", "revenue"], ["region", "units"])
        message = str(exc_info.value)
        assert "added" in message
        assert "removed" in message


class TestNextVersionNumber:
    def test_first_version_is_1(self, db):
        dataset = create_owned_dataset(db)
        assert _next_version_number(db, dataset.id) == 1

    def test_increments_past_existing_max(self, db):
        dataset = create_owned_dataset(db)
        db.add(DatasetVersion(dataset_id=dataset.id, version_number=1, file_path="x", row_count=1, column_count=1, uploaded_by=dataset.user_id, is_current=True))
        db.add(DatasetVersion(dataset_id=dataset.id, version_number=2, file_path="y", row_count=1, column_count=1, uploaded_by=dataset.user_id, is_current=False))
        db.commit()
        assert _next_version_number(db, dataset.id) == 3

    def test_scoped_to_its_own_dataset(self, db):
        dataset_a = create_owned_dataset(db, filename="a.csv")
        dataset_b = create_owned_dataset(db, filename="b.csv")
        db.add(DatasetVersion(dataset_id=dataset_a.id, version_number=5, file_path="x", row_count=1, column_count=1, uploaded_by=dataset_a.user_id, is_current=True))
        db.commit()
        # dataset_b has no versions of its own yet — dataset_a's high
        # version number must not leak across datasets.
        assert _next_version_number(db, dataset_b.id) == 1


class TestCreateInitialVersion:
    def test_creates_version_1_and_sets_current_version_number(self, db):
        dataset = create_owned_dataset(db)
        version = create_initial_version(db, dataset, dataset.user_id)

        assert version.version_number == 1
        assert version.is_current is True
        assert version.file_path == dataset.file_path
        assert version.row_count == dataset.row_count

        db.refresh(dataset)
        assert dataset.current_version_number == 1
