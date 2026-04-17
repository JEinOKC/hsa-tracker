"""S3 service for receipt/document storage.

Keys follow the pattern:
    {app_env}/{user_id}/{transaction_id}/{uuid}-{sanitized_filename}

This keeps a single bucket organised across dev/staging/production environments.
"""

import os
import re
import uuid as _uuid

import boto3
from botocore.exceptions import ClientError

from app.config import settings


def build_s3_key(app_env: str, user_id: str, transaction_id: str, filename: str) -> str:
    """Build a namespaced S3 object key for a transaction document.

    Strips path components (guards against traversal) then replaces any
    remaining characters outside [word chars, dot, dash] with underscores.
    """
    base = os.path.basename(filename) or "file"
    safe_name = re.sub(r"[^\w.\-]", "_", base)
    return f"{app_env}/{user_id}/{transaction_id}/{_uuid.uuid4()}-{safe_name}"


class S3Service:
    def __init__(self) -> None:
        self.client = boto3.client(
            "s3",
            region_name=settings.aws_s3_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            aws_session_token=settings.aws_session_token,
        )
        self.bucket = settings.aws_s3_bucket

    def generate_presigned_put_url(
        self, key: str, content_type: str, expires_in: int = 900
    ) -> str:
        """Return a presigned PUT URL the client uses to upload directly to S3 (15 min TTL)."""
        return self.client.generate_presigned_url(
            "put_object",
            Params={"Bucket": self.bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=expires_in,
        )

    def generate_presigned_get_url(self, key: str, expires_in: int = 3600) -> str:
        """Return a presigned GET URL for viewing a stored document (1 hr TTL)."""
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires_in,
        )

    def object_exists(self, key: str) -> bool:
        """Return True if the object exists in S3 (used to confirm upload completion)."""
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False

    def delete(self, key: str) -> None:
        """Delete an object from S3."""
        self.client.delete_object(Bucket=self.bucket, Key=key)


s3_service = S3Service()
