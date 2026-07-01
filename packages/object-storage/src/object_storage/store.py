from __future__ import annotations

import io
import logging
import os
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class ObjectStore(Protocol):
    enabled: bool

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str | None: ...
    def delete(self, key_or_url: str) -> None: ...


class NullStore:
    """Disabled storage: put returns None, delete is a no-op."""

    enabled = False

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str | None:
        return None

    def delete(self, key_or_url: str) -> None:
        return None


class MinioStore:
    """MinIO/S3 object store for call recordings."""

    enabled = True

    def __init__(self, client, bucket: str, endpoint: str, secure: bool) -> None:
        self._client = client
        self._bucket = bucket
        self._scheme = "https" if secure else "http"
        self._endpoint = endpoint

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str | None:
        self._client.put_object(self._bucket, key, io.BytesIO(data), length=len(data), content_type=content_type)
        return f"{self._scheme}://{self._endpoint}/{self._bucket}/{key}"

    def delete(self, key_or_url: str) -> None:
        key = key_or_url
        marker = f"/{self._bucket}/"
        if marker in key_or_url:
            key = key_or_url.split(marker, 1)[1]
        self._client.remove_object(self._bucket, key)


_store: ObjectStore | None = None


def get_store() -> ObjectStore:
    """Return the process object store (MinIO if configured, else a NullStore). Memoized."""
    global _store
    if _store is not None:
        return _store
    endpoint = os.getenv("MINIO_ENDPOINT")
    if not endpoint:
        _store = NullStore()
        return _store
    try:
        from minio import Minio  # optional dependency

        secure = os.getenv("MINIO_SECURE", "false").lower() == "true"
        bucket = os.getenv("MINIO_BUCKET", "call-recordings")
        client = Minio(
            endpoint,
            access_key=os.getenv("MINIO_ROOT_USER", "minioadmin"),
            secret_key=os.getenv("MINIO_ROOT_PASSWORD", "minioadmin"),
            secure=secure,
        )
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
        _store = MinioStore(client, bucket, endpoint, secure)
        logger.info("minio object storage enabled (bucket=%s)", bucket)
    except Exception as exc:  # noqa: BLE001
        logger.warning("minio unavailable (%s); recording storage disabled", exc)
        _store = NullStore()
    return _store