"""MinIO access for the knowledge bucket (RAG phase 3).

Deliberately separate from `packages/object-storage`, which is the *call-recordings* store: it
is memoized to one bucket, exposes only put/delete, and returns a NullStore when MinIO is absent
so a recording silently vanishes rather than failing a call. Knowledge ingestion needs the
opposite contract - list + get, a different bucket, and a loud failure when the store is missing,
because silently ingesting nothing would leave the agent answering from an empty index.
"""
from __future__ import annotations

import logging
import os

from knowledge_service.parsers import SUPPORTED_SUFFIXES  # single source of truth

logger = logging.getLogger(__name__)

DEFAULT_BUCKET = "telecom-knowledge"


class KnowledgeStoreError(RuntimeError):
    """The knowledge bucket is unreachable or misconfigured. Never degrade to 'no documents'."""


def knowledge_bucket() -> str:
    return os.getenv("KNOWLEDGE_MINIO_BUCKET", DEFAULT_BUCKET)


class KnowledgeStore:
    """List/get/put over the knowledge bucket, creating it on first use."""

    def __init__(self, client, bucket: str, endpoint: str, secure: bool) -> None:
        self._client = client
        self._bucket = bucket
        self._endpoint = endpoint
        self._scheme = "https" if secure else "http"

    @property
    def bucket(self) -> str:
        return self._bucket

    def uri(self, key: str) -> str:
        """Stable locator recorded on knowledge.documents.minio_uri."""
        return f"{self._scheme}://{self._endpoint}/{self._bucket}/{key}"

    def list_keys(self) -> list[str]:
        """Every ingestible object key in the bucket, sorted for deterministic runs."""
        try:
            objects = self._client.list_objects(self._bucket, recursive=True)
            keys = [
                obj.object_name
                for obj in objects
                if obj.object_name.lower().endswith(SUPPORTED_SUFFIXES)
            ]
        except Exception as exc:
            raise KnowledgeStoreError(f"cannot list bucket {self._bucket!r}: {exc}") from exc
        return sorted(keys)

    def get(self, key: str) -> bytes:
        response = None
        try:
            response = self._client.get_object(self._bucket, key)
            return response.read()
        except Exception as exc:
            raise KnowledgeStoreError(f"cannot read {key!r}: {exc}") from exc
        finally:
            if response is not None:
                response.close()
                response.release_conn()

    def put(self, key: str, data: bytes, content_type: str = "text/markdown") -> str:
        import io

        try:
            self._client.put_object(
                self._bucket, key, io.BytesIO(data), length=len(data), content_type=content_type
            )
        except Exception as exc:
            raise KnowledgeStoreError(f"cannot write {key!r}: {exc}") from exc
        return self.uri(key)


    def delete(self, key: str) -> None:
        """Remove an object. Idempotent: deleting an absent key is not an error."""
        try:
            self._client.remove_object(self._bucket, key)
        except Exception as exc:
            raise KnowledgeStoreError(f"cannot delete {key!r}: {exc}") from exc


def get_knowledge_store() -> KnowledgeStore:
    """Build the knowledge store, creating the bucket if absent. Raises if MinIO is unusable."""
    endpoint = os.getenv("MINIO_ENDPOINT")
    if not endpoint:
        raise KnowledgeStoreError("MINIO_ENDPOINT is not set; knowledge ingestion needs MinIO")
    try:
        from minio import Minio
    except ImportError as exc:
        raise KnowledgeStoreError(f"minio client is not installed: {exc}") from exc

    secure = os.getenv("MINIO_SECURE", "false").lower() == "true"
    bucket = knowledge_bucket()
    try:
        client = Minio(
            endpoint,
            access_key=os.getenv("MINIO_ROOT_USER", "minioadmin"),
            secret_key=os.getenv("MINIO_ROOT_PASSWORD", "minioadmin"),
            secure=secure,
        )
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
            logger.info("created knowledge bucket %s", bucket)
    except Exception as exc:
        raise KnowledgeStoreError(f"cannot reach MinIO at {endpoint}: {exc}") from exc
    return KnowledgeStore(client, bucket, endpoint, secure)
