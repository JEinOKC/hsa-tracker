"""S3 service for receipt file management"""

import boto3
from botocore.exceptions import ClientError
from typing import Optional
from datetime import timedelta
from uuid import UUID
import os

from app.config import settings


class S3Service:
    """Service for managing receipt files in S3"""

    def __init__(self):
        """Initialize S3 client"""
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_s3_region,
        )
        self.bucket_name = settings.aws_s3_bucket

    def generate_upload_url(
        self,
        file_name: str,
        mime_type: str,
        family_id: UUID,
        transaction_id: UUID,
        expires_in: int = 900  # 15 minutes
    ) -> dict:
        """
        Generate a pre-signed URL for uploading a file to S3

        Args:
            file_name: Original filename
            mime_type: MIME type of the file
            family_id: Family ID (for organizing files)
            transaction_id: Transaction ID
            expires_in: URL expiration time in seconds (default 15 minutes)

        Returns:
            dict with 'upload_url', 's3_key', and 'fields' for multipart upload
        """
        # Generate S3 key with organized structure
        # Format: receipts/{family_id}/{transaction_id}/{timestamp}_{filename}
        from datetime import datetime
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        file_extension = os.path.splitext(file_name)[1]
        s3_key = f"receipts/{family_id}/{transaction_id}/{timestamp}_{file_name}"

        try:
            # Generate pre-signed POST URL for upload
            presigned_post = self.s3_client.generate_presigned_post(
                Bucket=self.bucket_name,
                Key=s3_key,
                Fields={
                    "Content-Type": mime_type,
                    "acl": "private",
                },
                Conditions=[
                    {"Content-Type": mime_type},
                    {"acl": "private"},
                    ["content-length-range", 1, settings.max_upload_size_bytes],
                ],
                ExpiresIn=expires_in,
            )

            return {
                "upload_url": presigned_post["url"],
                "s3_key": s3_key,
                "fields": presigned_post["fields"],
            }

        except ClientError as e:
            raise Exception(f"Failed to generate upload URL: {str(e)}")

    def generate_download_url(
        self,
        s3_key: str,
        expires_in: int = 3600  # 1 hour
    ) -> str:
        """
        Generate a pre-signed URL for downloading a file from S3

        Args:
            s3_key: S3 object key
            expires_in: URL expiration time in seconds (default 1 hour)

        Returns:
            Pre-signed download URL
        """
        try:
            download_url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': s3_key,
                },
                ExpiresIn=expires_in,
            )

            return download_url

        except ClientError as e:
            raise Exception(f"Failed to generate download URL: {str(e)}")

    def delete_file(self, s3_key: str) -> bool:
        """
        Delete a file from S3

        Args:
            s3_key: S3 object key

        Returns:
            True if successful, False otherwise
        """
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=s3_key,
            )
            return True

        except ClientError as e:
            print(f"Error deleting file from S3: {str(e)}")
            return False

    def check_file_exists(self, s3_key: str) -> bool:
        """
        Check if a file exists in S3

        Args:
            s3_key: S3 object key

        Returns:
            True if file exists, False otherwise
        """
        try:
            self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=s3_key,
            )
            return True

        except ClientError:
            return False

    def get_file_size(self, s3_key: str) -> Optional[int]:
        """
        Get the size of a file in S3

        Args:
            s3_key: S3 object key

        Returns:
            File size in bytes, or None if file doesn't exist
        """
        try:
            response = self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=s3_key,
            )
            return response['ContentLength']

        except ClientError:
            return None


# Global S3 service instance
s3_service = S3Service()
