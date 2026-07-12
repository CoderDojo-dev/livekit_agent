"""Command-line entrypoints for knowledge bucket bootstrap and ingestion."""
from __future__ import annotations

import argparse

from knowledge_service.embeddings import NIMEmbeddingClient
from knowledge_service.ingestion import (
    KnowledgeIngestor,
    KnowledgeStorageConfig,
    ensure_knowledge_bucket,
    supported_objects,
)
from knowledge_service.qdrant_store import QdrantConfig


def bootstrap_bucket() -> None:
    storage = KnowledgeStorageConfig.from_env()
    client = storage.client()
    created = ensure_knowledge_bucket(client, storage)
    action = "CREATED" if created else "VERIFIED"
    print(f"MINIO_KNOWLEDGE_BUCKET_{action}={storage.bucket}")
    print("MINIO_KNOWLEDGE_BUCKET_GATE_PASSED")


def _build_ingestor() -> tuple[KnowledgeIngestor, KnowledgeStorageConfig, NIMEmbeddingClient]:
    storage = KnowledgeStorageConfig.from_env()
    embedder = NIMEmbeddingClient.from_env()
    qdrant = QdrantConfig.from_env()
    ingestor = KnowledgeIngestor(
        minio_client=storage.client(),
        storage=storage,
        embedder=embedder,
        qdrant_client=qdrant.client(),
        qdrant=qdrant,
    )
    return ingestor, storage, embedder


def ingest() -> None:
    parser = argparse.ArgumentParser(description="Ingest knowledge objects from MinIO")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--object", help="single object key to ingest")
    group.add_argument("--all", action="store_true", help="ingest every supported object")
    args = parser.parse_args()

    ingestor, storage, embedder = _build_ingestor()
    try:
        object_keys = (
            [args.object]
            if args.object
            else list(supported_objects(storage.client(), storage.bucket))
        )
        if not object_keys:
            raise SystemExit("FAIL: no supported knowledge objects found")
        for object_key in object_keys:
            result = ingestor.ingest_object(object_key)
            print(
                "INGESTED_OBJECT="
                f"{result.object_key} document_id={result.document_id} "
                f"version={result.version} chunks={result.chunks} "
                f"embedded={result.embedded} deduplicated={str(result.deduplicated).lower()}"
            )
    finally:
        embedder.close()
    print("KNOWLEDGE_INGESTION_PASSED")


if __name__ == "__main__":
    ingest()
