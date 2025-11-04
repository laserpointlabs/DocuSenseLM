"""
Storage service for MinIO/S3 operations
Abstracts file storage to support both local MinIO and AWS S3
"""
import os
from typing import Optional, BinaryIO
from minio import Minio
from minio.error import S3Error
import boto3
from botocore.exceptions import ClientError
from io import BytesIO


class StorageService:
    """Storage service for file operations"""

    def __init__(self):
        self.use_s3 = os.getenv("USE_S3", "false").lower() == "true"

        if self.use_s3:
            self._init_s3()
        else:
            self._init_minio()

    def _init_minio(self):
        """Initialize MinIO client"""
        endpoint = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
        access_key = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
        secret_key = os.getenv("MINIO_SECRET_KEY", "minioadmin")

        # Parse endpoint (remove http:// or https://)
        if endpoint.startswith("http://"):
            endpoint = endpoint[7:]
            secure = False
        elif endpoint.startswith("https://"):
            endpoint = endpoint[8:]
            secure = True
        else:
            secure = False

        self.client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure
        )
        self._ensure_buckets()

    def _init_s3(self):
        """Initialize AWS S3 client"""
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name=os.getenv("AWS_REGION", "us-east-1")
        )
        self.bucket_raw = os.getenv("S3_BUCKET_RAW", "nda-raw")
        self.bucket_processed = os.getenv("S3_BUCKET_PROCESSED", "nda-processed")
        self.bucket_logs = os.getenv("S3_BUCKET_LOGS", "nda-logs")
        self._ensure_buckets()

    def _ensure_buckets(self):
        """Ensure required buckets exist"""
        buckets = ["nda-raw", "nda-processed", "nda-logs"]

        if self.use_s3:
            for bucket in buckets:
                try:
                    self.s3_client.head_bucket(Bucket=bucket)
                except ClientError:
                    self.s3_client.create_bucket(Bucket=bucket)
        else:
            for bucket in buckets:
                if not self.client.bucket_exists(bucket):
                    self.client.make_bucket(bucket)

    def upload_file(self, bucket: str, object_name: str, file_data: bytes, content_type: str = "application/octet-stream") -> str:
        """Upload file to storage"""
        if self.use_s3:
            return self._upload_to_s3(bucket, object_name, file_data, content_type)
        else:
            return self._upload_to_minio(bucket, object_name, file_data, content_type)

    def _upload_to_minio(self, bucket: str, object_name: str, file_data: bytes, content_type: str) -> str:
        """Upload to MinIO"""
        try:
            self.client.put_object(
                bucket,
                object_name,
                BytesIO(file_data),
                length=len(file_data),
                content_type=content_type
            )
            return f"{bucket}/{object_name}"
        except S3Error as e:
            raise Exception(f"Failed to upload to MinIO: {e}")

    def _upload_to_s3(self, bucket: str, object_name: str, file_data: bytes, content_type: str) -> str:
        """Upload to S3"""
        try:
            self.s3_client.put_object(
                Bucket=bucket,
                Key=object_name,
                Body=file_data,
                ContentType=content_type
            )
            return f"s3://{bucket}/{object_name}"
        except ClientError as e:
            raise Exception(f"Failed to upload to S3: {e}")

    def download_file(self, bucket: str, object_name: str) -> bytes:
        """Download file from storage"""
        if self.use_s3:
            return self._download_from_s3(bucket, object_name)
        else:
            return self._download_from_minio(bucket, object_name)

    def _download_from_minio(self, bucket: str, object_name: str) -> bytes:
        """Download from MinIO"""
        try:
            response = self.client.get_object(bucket, object_name)
            data = response.read()
            response.close()
            response.release_conn()
            return data
        except S3Error as e:
            raise Exception(f"Failed to download from MinIO: {e}")

    def _download_from_s3(self, bucket: str, object_name: str) -> bytes:
        """Download from S3"""
        try:
            response = self.s3_client.get_object(Bucket=bucket, Key=object_name)
            return response['Body'].read()
        except ClientError as e:
            raise Exception(f"Failed to download from S3: {e}")

    def delete_file(self, bucket: str, object_name: str):
        """Delete file from storage"""
        if self.use_s3:
            try:
                self.s3_client.delete_object(Bucket=bucket, Key=object_name)
            except ClientError as e:
                raise Exception(f"Failed to delete from S3: {e}")
        else:
            try:
                self.client.remove_object(bucket, object_name)
            except S3Error as e:
                raise Exception(f"Failed to delete from MinIO: {e}")

    def file_exists(self, bucket: str, object_name: str) -> bool:
        """Check if file exists"""
        if self.use_s3:
            try:
                self.s3_client.head_object(Bucket=bucket, Key=object_name)
                return True
            except ClientError:
                return False
        else:
            try:
                self.client.stat_object(bucket, object_name)
                return True
            except S3Error:
                return False

    def get_file_url(self, bucket: str, object_name: str, expires_in: int = 3600) -> str:
        """Get presigned URL for file access"""
        if self.use_s3:
            try:
                url = self.s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': bucket, 'Key': object_name},
                    ExpiresIn=expires_in
                )
                return url
            except ClientError as e:
                raise Exception(f"Failed to generate S3 URL: {e}")
        else:
            try:
                url = self.client.presigned_get_object(bucket, object_name, expires=expires_in)
                return url
            except S3Error as e:
                raise Exception(f"Failed to generate MinIO URL: {e}")


# Global instance
storage_service = StorageService()
