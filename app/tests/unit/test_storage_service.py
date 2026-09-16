import os

import pytest
from botocore.exceptions import ClientError

from app.services import s3_service, storage_service
from app.services.storage_service import LocalStorageBackend, S3StorageBackend, get_storage_backend


class TestLocalStorageBackend:
    def test_save_then_load_round_trips(self, tmp_path):
        backend = LocalStorageBackend(root=str(tmp_path))
        key = backend.save(b"hello world", "sub/dir/file.csv")
        assert key == "sub/dir/file.csv"
        assert backend.load("sub/dir/file.csv") == b"hello world"

    def test_load_missing_file_raises(self, tmp_path):
        backend = LocalStorageBackend(root=str(tmp_path))
        with pytest.raises(FileNotFoundError):
            backend.load("nope.csv")

    def test_url_for_is_always_none(self, tmp_path):
        backend = LocalStorageBackend(root=str(tmp_path))
        backend.save(b"x", "a.csv")
        assert backend.url_for("a.csv") is None

    def test_delete_is_a_noop_when_file_missing(self, tmp_path):
        backend = LocalStorageBackend(root=str(tmp_path))
        backend.delete("never-existed.csv")  # must not raise

    def test_delete_removes_the_file(self, tmp_path):
        backend = LocalStorageBackend(root=str(tmp_path))
        backend.save(b"x", "a.csv")
        backend.delete("a.csv")
        with pytest.raises(FileNotFoundError):
            backend.load("a.csv")


class TestGetStorageBackend:
    def test_defaults_to_local(self, monkeypatch):
        monkeypatch.delenv("STORAGE_BACKEND", raising=False)
        assert isinstance(get_storage_backend(), LocalStorageBackend)

    def test_s3_env_selects_s3_backend(self, monkeypatch):
        monkeypatch.setenv("STORAGE_BACKEND", "s3")
        try:
            assert isinstance(get_storage_backend(), S3StorageBackend)
        finally:
            monkeypatch.delenv("STORAGE_BACKEND", raising=False)

    def test_local_storage_root_env_overrides_the_app_prefix(self, monkeypatch, tmp_path):
        monkeypatch.setenv("LOCAL_STORAGE_ROOT", str(tmp_path))
        backend = get_storage_backend("uploads")
        assert backend.root == tmp_path / "uploads"


class TestS3StorageBackend:
    def test_save_delegates_to_s3_service_with_prefix(self, s3_mock):
        backend = S3StorageBackend(prefix="uploads")
        key = backend.save(b"data", "1/file.csv")
        assert key == "uploads/1/file.csv"
        s3_mock.put_object.assert_called_once()
        assert s3_mock.put_object.call_args.kwargs["Key"] == "uploads/1/file.csv"

    def test_load_delegates_to_s3_service(self, s3_mock):
        s3_mock.get_object.return_value = {"Body": type("B", (), {"read": lambda self: b"csv bytes"})()}
        backend = S3StorageBackend(prefix="uploads")
        assert backend.load("1/file.csv") == b"csv bytes"

    def test_url_for_delegates_to_presigned_url(self, s3_mock):
        s3_mock.generate_presigned_url.return_value = "https://s3.example.com/signed"
        backend = S3StorageBackend(prefix="exports")
        assert backend.url_for("1/report.pdf") == "https://s3.example.com/signed"

    def test_delete_delegates_to_s3_service(self, s3_mock):
        backend = S3StorageBackend(prefix="uploads")
        backend.delete("1/file.csv")
        s3_mock.delete_object.assert_called_once()

    def test_no_prefix_leaves_key_unchanged(self, s3_mock):
        backend = S3StorageBackend()
        key = backend.save(b"data", "1/file.csv")
        assert key == "1/file.csv"


class TestS3ServiceErrorHandling:
    def test_upload_wraps_client_error(self, s3_mock):
        s3_mock.put_object.side_effect = ClientError({"Error": {"Code": "AccessDenied", "Message": "nope"}}, "PutObject")
        with pytest.raises(Exception, match="Failed to upload file to S3"):
            s3_service.upload_file_to_s3(b"data", "key.csv")

    def test_download_missing_key_raises_a_clear_message(self, s3_mock):
        s3_mock.get_object.side_effect = ClientError({"Error": {"Code": "NoSuchKey", "Message": "nope"}}, "GetObject")
        with pytest.raises(Exception, match="File not found in S3"):
            s3_service.download_file_from_s3("key.csv")

    def test_download_other_client_error_wraps_generically(self, s3_mock):
        s3_mock.get_object.side_effect = ClientError({"Error": {"Code": "AccessDenied", "Message": "nope"}}, "GetObject")
        with pytest.raises(Exception, match="Failed to download file from S3"):
            s3_service.download_file_from_s3("key.csv")

    def test_generate_presigned_url_wraps_client_error(self, s3_mock):
        s3_mock.generate_presigned_url.side_effect = ClientError({"Error": {"Code": "AccessDenied", "Message": "nope"}}, "GetObject")
        with pytest.raises(Exception, match="Failed to generate presigned URL"):
            s3_service.generate_presigned_url("key.csv")

    def test_delete_wraps_client_error(self, s3_mock):
        s3_mock.delete_object.side_effect = ClientError({"Error": {"Code": "AccessDenied", "Message": "nope"}}, "DeleteObject")
        with pytest.raises(Exception, match="Failed to delete file from S3"):
            s3_service.delete_file_from_s3("key.csv")

    def test_get_s3_key_format(self):
        assert s3_service.get_s3_key("42", "sales.csv") == "uploads/42/sales.csv"
