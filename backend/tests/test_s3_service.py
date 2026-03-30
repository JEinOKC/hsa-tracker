"""Unit tests for the S3 service layer.

Uses unittest.mock to mock the boto3 client — tests service logic and method
contracts without requiring a real or mocked AWS endpoint.
"""

import os
import uuid
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_S3_BUCKET", "test-bucket")
os.environ.setdefault("DATABASE_URL", "sqlite:///")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret")
os.environ.setdefault("WEBAUTHN_RP_ID", "localhost")
os.environ.setdefault("WEBAUTHN_RP_NAME", "Test")
os.environ.setdefault("WEBAUTHN_ORIGIN", "http://localhost:3001")


def _make_service(mock_client=None):
    """Return an S3Service with a patched boto3 client."""
    from app.services.s3 import S3Service
    if mock_client is None:
        mock_client = MagicMock()
    with patch("app.services.s3.boto3") as mock_boto3:
        mock_boto3.client.return_value = mock_client
        service = S3Service()
    return service, mock_client


# ---------------------------------------------------------------------------
# Presigned URLs
# ---------------------------------------------------------------------------

class TestPresignedUrls:
    def test_put_url_calls_generate_presigned_url_with_put_object(self):
        mock_client = MagicMock()
        mock_client.generate_presigned_url.return_value = "https://s3.example.com/put-url"
        service, _ = _make_service(mock_client)

        url = service.generate_presigned_put_url("some/key.jpg", "image/jpeg")

        assert url == "https://s3.example.com/put-url"
        mock_client.generate_presigned_url.assert_called_once_with(
            "put_object",
            Params={"Bucket": service.bucket, "Key": "some/key.jpg", "ContentType": "image/jpeg"},
            ExpiresIn=900,
        )

    def test_put_url_respects_custom_expiry(self):
        mock_client = MagicMock()
        mock_client.generate_presigned_url.return_value = "https://s3.example.com/url"
        service, _ = _make_service(mock_client)

        service.generate_presigned_put_url("k.jpg", "image/jpeg", expires_in=60)

        _, kwargs = mock_client.generate_presigned_url.call_args
        assert kwargs["ExpiresIn"] == 60

    def test_get_url_calls_generate_presigned_url_with_get_object(self):
        mock_client = MagicMock()
        mock_client.generate_presigned_url.return_value = "https://s3.example.com/get-url"
        service, _ = _make_service(mock_client)

        url = service.generate_presigned_get_url("some/key.jpg")

        assert url == "https://s3.example.com/get-url"
        mock_client.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={"Bucket": service.bucket, "Key": "some/key.jpg"},
            ExpiresIn=3600,
        )


# ---------------------------------------------------------------------------
# object_exists
# ---------------------------------------------------------------------------

class TestObjectExists:
    def test_returns_true_when_head_object_succeeds(self):
        mock_client = MagicMock()
        mock_client.head_object.return_value = {"ContentLength": 1024}
        service, _ = _make_service(mock_client)

        assert service.object_exists("dev/user/txn/file.jpg") is True
        mock_client.head_object.assert_called_once_with(
            Bucket=service.bucket, Key="dev/user/txn/file.jpg"
        )

    def test_returns_false_when_head_object_raises_client_error(self):
        mock_client = MagicMock()
        error_response = {"Error": {"Code": "404", "Message": "Not Found"}}
        mock_client.head_object.side_effect = ClientError(error_response, "HeadObject")
        service, _ = _make_service(mock_client)

        assert service.object_exists("missing/key.jpg") is False


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------

class TestDelete:
    def test_delete_calls_delete_object(self):
        mock_client = MagicMock()
        service, _ = _make_service(mock_client)

        service.delete("dev/user/txn/receipt.pdf")

        mock_client.delete_object.assert_called_once_with(
            Bucket=service.bucket, Key="dev/user/txn/receipt.pdf"
        )


# ---------------------------------------------------------------------------
# build_s3_key
# ---------------------------------------------------------------------------

class TestBuildS3Key:
    def test_key_starts_with_env_user_txn(self):
        from app.services.s3 import build_s3_key
        key = build_s3_key("development", "user-abc", "txn-xyz", "receipt.jpg")
        assert key.startswith("development/user-abc/txn-xyz/")

    def test_key_has_exactly_four_segments(self):
        from app.services.s3 import build_s3_key
        key = build_s3_key("production", "u1", "t1", "file.pdf")
        parts = key.split("/")
        assert len(parts) == 4

    def test_key_contains_uuid_in_filename_segment(self):
        from app.services.s3 import build_s3_key
        key = build_s3_key("dev", "u", "t", "file.jpg")
        filename_segment = key.split("/")[-1]
        # Format: <uuid>-file.jpg
        assert filename_segment.endswith("-file.jpg")
        # Ensure the prefix is a valid UUID
        uuid_part = filename_segment[:-len("-file.jpg")]
        uuid.UUID(uuid_part)  # raises ValueError if invalid

    def test_sanitises_special_characters(self):
        from app.services.s3 import build_s3_key
        key = build_s3_key("dev", "u", "t", "my receipt (2024).jpg")
        filename = key.split("/")[-1]
        assert " " not in filename
        assert "(" not in filename
        assert ")" not in filename

    def test_sanitises_path_traversal(self):
        from app.services.s3 import build_s3_key
        key = build_s3_key("dev", "u", "t", "../../../etc/passwd")
        parts = key.split("/")
        assert len(parts) == 4, f"Expected 4 path segments, got: {key}"
        filename = parts[-1]
        assert ".." not in filename
        assert "/" not in filename

    def test_different_calls_produce_unique_keys(self):
        from app.services.s3 import build_s3_key
        key1 = build_s3_key("dev", "u", "t", "file.jpg")
        key2 = build_s3_key("dev", "u", "t", "file.jpg")
        assert key1 != key2
