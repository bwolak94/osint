"""MinIO storage adapter for file operations."""

from io import BytesIO

from minio import Minio

from src.config import get_settings


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
