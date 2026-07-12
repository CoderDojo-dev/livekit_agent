"""On-demand MinIO to Postgres to Qdrant knowledge ingestion."""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from typing import Iterator

from minio import Minio
from qdrant_client import QdrantClient, models
from sqlalchemy import func, select

from knowledge_service.documents import ParsedDocument, chunk_document, parse_document
from knowledge_service.embeddings import NIMEmbeddingClient
from knowledge_service.qdrant_store import QdrantConfig, verify_collection
from persistence import session_scope
from persistence.models.knowledge import (
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeIngestionJob,
    KnowledgeSyncOutbox,
)


class KnowledgeIngestionError(RuntimeError):
    """Raised when an object cannot be ingested consistently."""


@dataclass(frozen=True, slots=True)
class KnowledgeStorageConfig:
    endpoint: str
    access_key: str
    secret_key: str
    bucket: str = "telecom-knowledge"
    secure: bool = False

    @classmethod
    def from_env(cls) -> KnowledgeStorageConfig:
        endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9000").strip()
        bucket = os.getenv("MINIO_KNOWLEDGE_BUCKET", "telecom-knowledge").strip()
        if not endpoint:
            raise KnowledgeIngestionError("MINIO_ENDPOINT is required")
        if not bucket or bucket == os.getenv("MINIO_BUCKET", "call-recordings"):
            raise KnowledgeIngestionError(
                "MINIO_KNOWLEDGE_BUCKET must be set and separate from MINIO_BUCKET"
            )
        return cls(
            endpoint=endpoint,
            access_key=os.getenv("MINIO_ROOT_USER", "minioadmin"),
            secret_key=os.getenv("MINIO_ROOT_PASSWORD", "minioadmin"),
            bucket=bucket,
            secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
        )

    def client(self) -> Minio:
        return Minio(
            self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure,
        )

    @property
    def scheme(self) -> str:
        return "https" if self.secure else "http"


def ensure_knowledge_bucket(client: Minio, config: KnowledgeStorageConfig) -> bool:
    """Create the dedicated private knowledge bucket if absent."""
    if client.bucket_exists(config.bucket):
        return False
    client.make_bucket(config.bucket)
    return True


def read_object(client: Minio, bucket: str, object_key: str) -> tuple[bytes, dict[str, str]]:
    """Read one MinIO object and always release the HTTP connection."""
    response = client.get_object(bucket, object_key)
    try:
        data = response.read()
    finally:
        response.close()
        response.release_conn()
    stat = client.stat_object(bucket, object_key)
    return data, dict(stat.metadata or {})


@dataclass(frozen=True, slots=True)
class IngestionResult:
    object_key: str
    document_id: uuid.UUID
    version: int
    chunks: int
    embedded: int
    deduplicated: bool


class KnowledgeIngestor:
    """Fail-closed ingestion coordinator with checksum idempotency."""

    def __init__(
        self,
        *,
        minio_client: Minio,
        storage: KnowledgeStorageConfig,
        embedder: NIMEmbeddingClient,
        qdrant_client: QdrantClient,
        qdrant: QdrantConfig,
        chunk_tokens: int = 512,
        overlap_tokens: int = 64,
        embedding_batch_size: int = 32,
    ) -> None:
        if embedding_batch_size < 1:
            raise ValueError("embedding_batch_size must be positive")
        self._minio = minio_client
        self._storage = storage
        self._embedder = embedder
        self._qdrant = qdrant_client
        self._qdrant_config = qdrant
        self._chunk_tokens = chunk_tokens
        self._overlap_tokens = overlap_tokens
        self._batch_size = embedding_batch_size

    def ingest_object(self, object_key: str) -> IngestionResult:
        ensure_knowledge_bucket(self._minio, self._storage)
        verify_collection(self._qdrant, self._qdrant_config)
        data, object_metadata = read_object(
            self._minio,
            self._storage.bucket,
            object_key,
        )
        document = parse_document(object_key, data, object_metadata)

        existing = self._ready_duplicate(document)
        if existing is not None:
            self._record_deduplicated_job(existing, object_key)
            return IngestionResult(
                object_key=object_key,
                document_id=existing.id,
                version=existing.version,
                chunks=0,
                embedded=0,
                deduplicated=True,
            )

        chunks = chunk_document(
            document,
            chunk_tokens=self._chunk_tokens,
            overlap_tokens=self._overlap_tokens,
        )
        vectors = self._embed_chunks(chunks)
        document_id = uuid.uuid4()
        job_id = uuid.uuid4()
        version = self._next_version(object_key)
        points: list[models.PointStruct] = []
        outbox_ids: list[uuid.UUID] = []

        minio_uri = (
            f"{self._storage.scheme}://{self._storage.endpoint}/"
            f"{self._storage.bucket}/{object_key}"
        )
        try:
            with session_scope() as session:
                row = KnowledgeDocument(
                    id=document_id,
                    source=document.source,
                    title=document.title,
                    language=document.language,
                    document_type=document.document_type,
                    checksum=document.checksum,
                    version=version,
                    status="processing",
                    minio_uri=minio_uri,
                    metadata_json=document.metadata,
                )
                session.add(row)
                session.add(
                    KnowledgeIngestionJob(
                        id=job_id,
                        document_id=document_id,
                        status="running",
                        source_object_key=object_key,
                        document_count=1,
                        chunk_count=len(chunks),
                        embedded_count=len(vectors),
                        embedding_model=self._embedder.config.model,
                        embedding_dimensions=self._embedder.config.dimensions,
                        started_at=func.now(),
                    )
                )

                for chunk, vector in zip(chunks, vectors, strict=True):
                    chunk_id = uuid.uuid4()
                    payload = self._payload(document, document_id, version, chunk, chunk_id)
                    session.add(
                        KnowledgeChunk(
                            id=chunk_id,
                            document_id=document_id,
                            ordinal=chunk.ordinal,
                            text_content=chunk.text,
                            token_count=chunk.token_count,
                            checksum=chunk.checksum,
                            qdrant_point_id=chunk_id,
                            embedding_model=self._embedder.config.model,
                            embedding_dimensions=self._embedder.config.dimensions,
                            metadata_json=chunk.metadata,
                            active=True,
                        )
                    )
                    outbox_id = uuid.uuid4()
                    outbox_ids.append(outbox_id)
                    session.add(
                        KnowledgeSyncOutbox(
                            id=outbox_id,
                            aggregate_type="chunk",
                            aggregate_id=chunk_id,
                            operation="upsert",
                            payload={"point_id": str(chunk_id), "vector": vector, "payload": payload},
                            status="pending",
                            attempt_count=0,
                        )
                    )
                    points.append(
                        models.PointStruct(id=str(chunk_id), vector=vector, payload=payload)
                    )

            self._qdrant.upsert(
                collection_name=self._qdrant_config.collection,
                points=points,
                wait=True,
            )
            self._mark_succeeded(document_id, job_id, outbox_ids)
        except Exception as exc:
            self._mark_failed(document_id, job_id, outbox_ids, str(exc))
            raise KnowledgeIngestionError(
                f"ingestion failed for {object_key!r}: {exc}"
            ) from exc

        return IngestionResult(
            object_key=object_key,
            document_id=document_id,
            version=version,
            chunks=len(chunks),
            embedded=len(vectors),
            deduplicated=False,
        )

    def _ready_duplicate(self, document: ParsedDocument) -> KnowledgeDocument | None:
        with session_scope() as session:
            return session.scalar(
                select(KnowledgeDocument)
                .where(
                    KnowledgeDocument.source == document.source,
                    KnowledgeDocument.checksum == document.checksum,
                    KnowledgeDocument.status == "ready",
                )
                .order_by(KnowledgeDocument.version.desc())
                .limit(1)
            )

    def _next_version(self, source: str) -> int:
        with session_scope() as session:
            current = session.scalar(
                select(func.max(KnowledgeDocument.version)).where(
                    KnowledgeDocument.source == source
                )
            )
            return int(current or 0) + 1

    def _record_deduplicated_job(self, document: KnowledgeDocument, object_key: str) -> None:
        with session_scope() as session:
            session.add(
                KnowledgeIngestionJob(
                    id=uuid.uuid4(),
                    document_id=document.id,
                    status="succeeded",
                    source_object_key=object_key,
                    document_count=0,
                    chunk_count=0,
                    embedded_count=0,
                    embedding_model=self._embedder.config.model,
                    embedding_dimensions=self._embedder.config.dimensions,
                    started_at=func.now(),
                    completed_at=func.now(),
                )
            )

    def _embed_chunks(self, chunks) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(chunks), self._batch_size):
            batch = chunks[start : start + self._batch_size]
            vectors.extend(self._embedder.embed_passages([chunk.text for chunk in batch]))
        return vectors

    @staticmethod
    def _payload(document, document_id, version, chunk, chunk_id) -> dict[str, object]:
        metadata = dict(document.metadata)
        return {
            "chunk_id": str(chunk_id),
            "document_id": str(document_id),
            "text": chunk.text,
            "ordinal": chunk.ordinal,
            "source": document.source,
            "title": document.title,
            "version": version,
            "language": document.language,
            "document_type": document.document_type,
            "applicable_plans": metadata.get("applicable_plans", []),
            "product_codes": metadata.get("product_codes", []),
            "regions": metadata.get("regions", []),
            "valid_from": metadata.get("valid_from"),
            "valid_until": metadata.get("valid_until"),
            "checksum": chunk.checksum,
            "active": True,
        }

    @staticmethod
    def _mark_succeeded(document_id, job_id, outbox_ids) -> None:
        with session_scope() as session:
            document = session.get(KnowledgeDocument, document_id)
            job = session.get(KnowledgeIngestionJob, job_id)
            if document is None or job is None:
                raise KnowledgeIngestionError("ingestion state disappeared before completion")
            document.status = "ready"
            job.status = "succeeded"
            job.completed_at = func.now()
            for outbox_id in outbox_ids:
                event = session.get(KnowledgeSyncOutbox, outbox_id)
                if event is not None:
                    event.status = "succeeded"
                    event.attempt_count = 1
                    event.processed_at = func.now()

    @staticmethod
    def _mark_failed(document_id, job_id, outbox_ids, error: str) -> None:
        try:
            with session_scope() as session:
                document = session.get(KnowledgeDocument, document_id)
                job = session.get(KnowledgeIngestionJob, job_id)
                if document is not None:
                    document.status = "failed"
                if job is not None:
                    job.status = "failed"
                    job.error_details = error[:4000]
                    job.completed_at = func.now()
                for outbox_id in outbox_ids:
                    event = session.get(KnowledgeSyncOutbox, outbox_id)
                    if event is not None:
                        event.status = "pending"
                        event.attempt_count += 1
                        event.last_error = error[:4000]
        except Exception:
            pass


def supported_objects(client: Minio, bucket: str) -> Iterator[str]:
    for item in client.list_objects(bucket, recursive=True):
        if item.object_name.lower().endswith((".pdf", ".md", ".markdown", ".txt")):
            yield item.object_name
