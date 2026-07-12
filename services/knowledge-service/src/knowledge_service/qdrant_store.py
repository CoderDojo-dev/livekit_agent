"""Qdrant collection bootstrap and readiness validation."""
from __future__ import annotations

import os
from dataclasses import dataclass

from qdrant_client import QdrantClient, models

from knowledge_service.embeddings import REQUIRED_EMBEDDING_DIMENSIONS

PAYLOAD_INDEXES: dict[str, models.PayloadSchemaType] = {
    "language": models.PayloadSchemaType.KEYWORD,
    "document_type": models.PayloadSchemaType.KEYWORD,
    "source": models.PayloadSchemaType.KEYWORD,
    "active": models.PayloadSchemaType.BOOL,
}


class QdrantCollectionError(RuntimeError):
    """Raised when the knowledge collection is absent or incompatible."""


@dataclass(frozen=True, slots=True)
class QdrantConfig:
    url: str = "http://localhost:6333"
    collection: str = "telecom_knowledge"
    dimensions: int = REQUIRED_EMBEDDING_DIMENSIONS
    timeout_seconds: float = 10.0

    @classmethod
    def from_env(cls) -> QdrantConfig:
        config = cls(
            url=os.getenv("QDRANT_URL", "http://localhost:6333").strip().rstrip("/"),
            collection=os.getenv("QDRANT_COLLECTION", "telecom_knowledge").strip(),
            dimensions=int(os.getenv("EMBEDDING_DIMENSIONS", "384")),
            timeout_seconds=float(os.getenv("QDRANT_TIMEOUT_S", "10")),
        )
        config.validate()
        return config

    def validate(self) -> None:
        if not self.url.startswith(("https://", "http://")):
            raise QdrantCollectionError("QDRANT_URL must be an HTTP(S) URL")
        if not self.collection:
            raise QdrantCollectionError("QDRANT_COLLECTION is required")
        if self.dimensions != REQUIRED_EMBEDDING_DIMENSIONS:
            raise QdrantCollectionError(
                f"EMBEDDING_DIMENSIONS must be {REQUIRED_EMBEDDING_DIMENSIONS}, "
                f"got {self.dimensions}"
            )
        if self.timeout_seconds <= 0:
            raise QdrantCollectionError("QDRANT_TIMEOUT_S must be positive")

    def client(self) -> QdrantClient:
        return QdrantClient(url=self.url, timeout=self.timeout_seconds)


def verify_collection(client: QdrantClient, config: QdrantConfig) -> None:
    """Raise unless the collection exists with 384-dimensional cosine vectors."""
    config.validate()
    if not client.collection_exists(config.collection):
        raise QdrantCollectionError(
            f"Qdrant collection {config.collection!r} does not exist"
        )

    info = client.get_collection(config.collection)
    vectors = info.config.params.vectors
    if isinstance(vectors, dict):
        raise QdrantCollectionError("named vectors are not supported for telecom_knowledge")
    if vectors.size != config.dimensions:
        raise QdrantCollectionError(
            f"Qdrant collection has vector size {vectors.size}; expected {config.dimensions}"
        )
    if vectors.distance != models.Distance.COSINE:
        raise QdrantCollectionError(
            f"Qdrant collection uses {vectors.distance}; expected cosine distance"
        )


def bootstrap_collection(client: QdrantClient, config: QdrantConfig) -> bool:
    """Create the collection and payload indexes without destroying existing data.

    Returns True when the collection was created and False when it already existed.
    Existing incompatible collections fail closed rather than being recreated.
    """
    config.validate()
    created = False
    if not client.collection_exists(config.collection):
        client.create_collection(
            collection_name=config.collection,
            vectors_config=models.VectorParams(
                size=config.dimensions,
                distance=models.Distance.COSINE,
            ),
            hnsw_config=models.HnswConfigDiff(
                m=16,
                ef_construct=100,
                full_scan_threshold=10_000,
            ),
        )
        created = True

    verify_collection(client, config)
    for field_name, schema in PAYLOAD_INDEXES.items():
        client.create_payload_index(
            collection_name=config.collection,
            field_name=field_name,
            field_schema=schema,
            wait=True,
        )
    return created


def run_bootstrap() -> None:
    """Console entrypoint for idempotent collection bootstrap."""
    config = QdrantConfig.from_env()
    client = config.client()
    try:
        created = bootstrap_collection(client, config)
    finally:
        client.close()
    action = "created" if created else "verified"
    print(
        f"QDRANT_COLLECTION_{action.upper()}="
        f"{config.collection}:{config.dimensions}:cosine"
    )
    print("QDRANT_BOOTSTRAP_PASSED")


if __name__ == "__main__":
    run_bootstrap()
