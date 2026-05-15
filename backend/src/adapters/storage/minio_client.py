"""MinIO storage adapter for file operations.

Provides both a high-level ``MinioStorageClient`` for application use and
lower-level factory helpers (``build_minio_client``, ``ensure_bucket``) that
``main.py`` lifespan uses so the Minio client is never constructed inline. (#10)
"""

import asyncio
from io import BytesIO

import structlog
from minio import Minio

from src.config import Settings, get_settings

log = structlog.get_logger(__name__)


class MinioStorageClient:
    """Wrapper around the MinIO Python client for file upload/download/delete."""

    def __init__(self) -> None:
        settings = get_settings()
        self._client = Minio(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        self._bucket = settings.minio_bucket
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        """Create the default bucket if it does not exist."""
        if not self._client.bucket_exists(self._bucket):
            self._client.make_bucket(self._bucket)

    def upload_file(self, object_name: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        """Upload a file to MinIO.

        Args:
            object_name: The key / path in the bucket.
            data: Raw bytes to upload.
            content_type: MIME type of the file.

        Returns:
            The object name that was stored.
        """
        stream = BytesIO(data)
        self._client.put_object(
            bucket_name=self._bucket,
            object_name=object_name,
            data=stream,
            length=len(data),
            content_type=content_type,
        )
        return object_name

    def download_file(self, object_name: str) -> bytes:
        """Download a file from MinIO and return its contents as bytes."""
        response = self._client.get_object(self._bucket, object_name)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def delete_file(self, object_name: str) -> None:
        """Delete a file from MinIO."""
        self._client.remove_object(self._bucket, object_name)


# ---------------------------------------------------------------------------
# Lifespan helpers — used by main.py to avoid inline construction. (#10)
# ---------------------------------------------------------------------------


def build_minio_client(settings: Settings) -> Minio:
    """Return a configured Minio client from application settings."""
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


async def ensure_bucket(client: Minio, bucket: str) -> None:
    """Create *bucket* if it does not already exist (runs in executor thread pool)."""
    loop = asyncio.get_running_loop()
    found = await loop.run_in_executor(None, client.bucket_exists, bucket)
    if not found:
        await loop.run_in_executor(None, client.make_bucket, bucket)
        log.info("minio_bucket_created", bucket=bucket)
    else:
        log.debug("minio_bucket_exists", bucket=bucket)
