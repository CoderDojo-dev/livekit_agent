"""Fail-closed MinIO access for the dedicated knowledge bucket."""
from __future__ import annotations

import os
from dataclasses import dataclass
from io import BytesIO
from typing import Any

from minio import Minio


class KnowledgeStorageError(RuntimeError):
    """Raised when dedicated knowledge storage is unavailable or invalid."""


@dataclass(frozen=True, slots=True)
class KnowledgeStorageConfig:
    endpoint: str = "localhost:9000"
    access_key: str = "minioadmin"
    secret_key: str = "minioadmin"
    bucket: str = "telecom-knowledge"
    secure: bool = False

    @classmethod
    def from_env(cls) -> KnowledgeStorageConfig:
        config = cls(
            endpoint=os.getenv("MINIO_ENDPOINT", "localhost:9000").strip(),
            access_key=os.getenv("MINIO_ROOT_USER", "minioadmin").strip(),
            secret_key=os.getenv("MINIO_ROOT_PASSWORD", "minioadmin").strip(),
            bucket=os.getenv("KNOWLEDGE_MINIO_BUCKET", "telecom-knowledge").strip(),
            secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
        )
        if not config.endpoint or not config.access_key or not config.secret_key:
            raise KnowledgeStorageError("MinIO endpoint and credentials are required")
        if config.bucket == os.getenv("MINIO_BUCKET", "call-recordings"):
            raise KnowledgeStorageError(
                "KNOWLEDGE_MINIO_BUCKET must be separate from the recordings bucket"
            )
        return config


class KnowledgeObjectStore:
    """Small strict adapter around one dedicated MinIO bucket."""

    def __init__(self, config: KnowledgeStorageConfig, client: Minio | None = None) -> None:
        self.config = config
        self.client = client or Minio(
            config.endpoint,
            access_key=config.access_key,
            secret_key=config.secret_key,
            secure=config.secure,
        )

    @classmethod
    def from_env(cls) -> KnowledgeObjectStore:
        return cls(KnowledgeStorageConfig.from_env())

    def ensure_bucket(self) -> bool:
        """Create the bucket when absent. Return True only when created."""
        if self.client.bucket_exists(self.config.bucket):
            return False
        self.client.make_bucket(self.config.bucket)
        return True

    def read(self, key: str) -> tuple[bytes, dict[str, str]]:
        """Read one object and its user metadata, closing the response reliably."""
        if not key or key.endswith("/"):
            raise KnowledgeStorageError("a concrete MinIO object key is required")
        response = self.client.get_object(self.config.bucket, key)
        try:
            data = response.read()
        finally:
            response.close()
            response.release_conn()
        stat = self.client.stat_object(self.config.bucket, key)
        metadata = {
            str(k).lower().removeprefix("x-amz-meta-"): str(v)
            for k, v in (stat.metadata or {}).items()
        }
        metadata["content_type"] = stat.content_type or "application/octet-stream"
        return data, metadata

    def put(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str,
        metadata: dict[str, str] | None = None,
    ) -> str:
        self.client.put_object(
            self.config.bucket,
            key,
            BytesIO(data),
            length=len(data),
            content_type=content_type,
            metadata=metadata,
        )
        return f"minio://{self.config.bucket}/{key}"

    def list_keys(self, prefix: str = "") -> list[str]:
        return [
            item.object_name
            for item in self.client.list_objects(
                self.config.bucket,
                prefix=prefix,
                recursive=True,
            )
            if item.object_name and not item.object_name.endswith("/")
        ]


def bootstrap_knowledge_bucket() -> None:
    store = KnowledgeObjectStore.from_env()
    created = store.ensure_bucket()
    action = "CREATED" if created else "VERIFIED"
    print(f"KNOWLEDGE_BUCKET_{action}={store.config.bucket}")
    print("KNOWLEDGE_BUCKET_GATE_PASSED")


if __name__ == "__main__":
    bootstrap_knowledge_bucket()
