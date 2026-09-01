import os
import uuid
from abc import ABC, abstractmethod
from typing import Optional
from app.core.config import settings

class StorageProvider(ABC):
    """Abstract interface for immutable evidentiary object storage."""

    @abstractmethod
    def upload_file(self, file_bytes: bytes, filename: str, content_type: str = "image/jpeg") -> str:
        """Store file bytes and return access URL/URI."""
        pass

    @abstractmethod
    def get_file(self, file_path_or_key: str) -> bytes:
        """Retrieve stored file bytes by key/path."""
        pass


class LocalStorageProvider(StorageProvider):
    """Local filesystem storage provider for development and standalone edge deployment."""

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = os.path.abspath(base_dir or settings.STORAGE_LOCAL_DIR)
        os.makedirs(self.base_dir, exist_ok=True)

    def upload_file(self, file_bytes: bytes, filename: str, content_type: str = "image/jpeg") -> str:
        unique_name = f"{uuid.uuid4()}_{filename}"
        file_path = os.path.join(self.base_dir, unique_name)
        with open(file_path, "wb") as f:
            f.write(file_bytes)
        # Return URL relative to static mount
        return f"/static/uploads/{unique_name}"

    def get_file(self, file_path_or_key: str) -> bytes:
        filename = os.path.basename(file_path_or_key)
        full_path = os.path.join(self.base_dir, filename)
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"File not found in local storage: {full_path}")
        with open(full_path, "rb") as f:
            return f.read()


class S3StorageProvider(StorageProvider):
    """Production S3-compatible object storage provider (AWS S3, MinIO, Cloudflare R2)."""

    def __init__(self):
        try:
            import boto3
            self.s3_client = boto3.client(
                "s3",
                region_name=settings.S3_REGION,
                endpoint_url=settings.S3_ENDPOINT_URL,
                aws_access_key_id=settings.S3_ACCESS_KEY,
                aws_secret_access_key=settings.S3_SECRET_KEY,
            )
            self.bucket_name = settings.S3_BUCKET_NAME
        except ImportError:
            raise RuntimeError("boto3 package is required for S3StorageProvider. Install boto3 to use S3 storage backend.")

    def upload_file(self, file_bytes: bytes, filename: str, content_type: str = "image/jpeg") -> str:
        key = f"scans/{uuid.uuid4()}_{filename}"
        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=key,
            Body=file_bytes,
            ContentType=content_type
        )
        if settings.S3_ENDPOINT_URL:
            return f"{settings.S3_ENDPOINT_URL}/{self.bucket_name}/{key}"
        return f"https://{self.bucket_name}.s3.{settings.S3_REGION}.amazonaws.com/{key}"

    def get_file(self, file_path_or_key: str) -> bytes:
        key = file_path_or_key.split(f"{self.bucket_name}/")[-1]
        response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
        return response["Body"].read()


def get_storage_provider() -> StorageProvider:
    """Factory helper to obtain configured storage provider."""
    if settings.STORAGE_BACKEND.lower() == "s3":
        return S3StorageProvider()
    return LocalStorageProvider()
