"""On-demand, idempotent MinIO to Postgres/NIM/Qdrant ingestion pipeline."""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from qdrant_client import models as qmodels
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from knowledge_service.documents import ParsedDocument, chunk_document, parse_document
from knowledge_service.embeddings import NIMEmbeddingClient
from knowledge_service.knowledge_storage import KnowledgeObjectStore
from knowledge_service.qdrant_store import QdrantConfig, verify_collection
from persistence.engine import session_scope
from persistence.models.knowledge import (
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeIngestionJob,
    KnowledgeSyncOutbox,
)


@dataclass(frozen=True, slots=True)
class IngestionResult:
    object_key: str
    status: str
    document_id: str | None = None
    version: int | None = None
    chunk_count: int = 0


class KnowledgeIngestor:
    def __init__(
        self,
        *,
        store: KnowledgeObjectStore,
        embedder: NIMEmbeddingClient,
        qdrant_client: Any,
        qdrant_config: QdrantConfig,
        batch_size: int = 32,
        chunk_tokens: int = 512,
        overlap_tokens: int = 64,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        self.store = store
        self.embedder = embedder
        self.qdrant_client = qdrant_client
        self.qdrant_config = qdrant_config
        self.batch_size = batch_size
        self.chunk_tokens = chunk_tokens
        self.overlap_tokens = overlap_tokens

    @classmethod
    def from_env(cls) -> KnowledgeIngestor:
        store = KnowledgeObjectStore.from_env()
        store.ensure_bucket()
        embedder = NIMEmbeddingClient.from_env()
        qdrant_config = QdrantConfig.from_env()
        qdrant_client = qdrant_config.client()
        verify_collection(qdrant_client, qdrant_config)
        return cls(
            store=store,
            embedder=embedder,
            qdrant_client=qdrant_client,
            qdrant_config=qdrant_config,
            batch_size=int(os.getenv("KNOWLEDGE_EMBED_BATCH_SIZE", "32")),
            chunk_tokens=int(os.getenv("KNOWLEDGE_CHUNK_TOKENS", "512")),
            overlap_tokens=int(os.getenv("KNOWLEDGE_CHUNK_OVERLAP", "64")),
        )

    def close(self) -> None:
        self.embedder.close()
        self.qdrant_client.close()

    def ingest(self, object_key: str) -> IngestionResult:
        data, metadata = self.store.read(object_key)
        parsed = parse_document(object_key, data, metadata)

        with session_scope() as session:
            existing = session.scalar(
                select(KnowledgeDocument).where(
                    KnowledgeDocument.checksum == parsed.checksum,
                    KnowledgeDocument.status == "ready",
                )
            )
            if existing is not None:
                return IngestionResult(
                    object_key=object_key,
                    status="unchanged",
                    document_id=str(existing.id),
                    version=existing.version,
                )
            job = KnowledgeIngestionJob(
                status="running",
                source_object_key=object_key,
                embedding_model=self.embedder.config.model,
                embedding_dimensions=self.embedder.config.dimensions,
                started_at=datetime.now(UTC),
            )
            session.add(job)
            session.flush()
            job_id = job.id

        try:
            return self._ingest_new(job_id, parsed)
        except Exception as exc:
            with session_scope() as session:
                failed_job = session.get(KnowledgeIngestionJob, job_id)
                if failed_job is not None:
                    failed_job.status = "failed"
                    failed_job.error_details = str(exc)[:4000]
                    failed_job.completed_at = datetime.now(UTC)
            raise

    def _ingest_new(self, job_id: uuid.UUID, parsed: ParsedDocument) -> IngestionResult:
        chunks = chunk_document(
            parsed.text,
            chunk_tokens=self.chunk_tokens,
            overlap_tokens=self.overlap_tokens,
        )
        vectors: list[list[float]] = []
        for start in range(0, len(chunks), self.batch_size):
            vectors.extend(
                self.embedder.embed_passages(
                    [chunk.text for chunk in chunks[start : start + self.batch_size]]
                )
            )
        if len(vectors) != len(chunks):
            raise RuntimeError("embedding count does not match chunk count")

        with session_scope() as session:
            version = int(
                session.scalar(
                    select(func.max(KnowledgeDocument.version)).where(
                        KnowledgeDocument.source == parsed.source
                    )
                )
                or 0
            ) + 1
            document = KnowledgeDocument(
                source=parsed.source,
                title=parsed.title,
                language=parsed.language,
                document_type=parsed.document_type,
                checksum=parsed.checksum,
                version=version,
                status="processing",
                minio_uri=f"minio://{self.store.config.bucket}/{parsed.source}",
                metadata_json=parsed.metadata,
            )
            session.add(document)
            session.flush()

            points: list[qmodels.PointStruct] = []
            outbox_ids: list[uuid.UUID] = []
            for chunk, vector in zip(chunks, vectors, strict=True):
                row = KnowledgeChunk(
                    document_id=document.id,
                    ordinal=chunk.ordinal,
                    text_content=chunk.text,
                    token_count=chunk.token_count,
                    checksum=chunk.checksum,
                    qdrant_point_id=uuid.uuid4(),
                    embedding_model=self.embedder.config.model,
                    embedding_dimensions=self.embedder.config.dimensions,
                    metadata_json={},
                    active=True,
                )
                session.add(row)
                session.flush()
                payload = self._payload(document, row, parsed)
                outbox = KnowledgeSyncOutbox(
                    aggregate_type="chunk",
                    aggregate_id=row.id,
                    operation="upsert",
                    payload={"point_id": str(row.qdrant_point_id), "vector": vector, "payload": payload},
                    status="pending",
                )
                session.add(outbox)
                session.flush()
                outbox_ids.append(outbox.id)
                points.append(
                    qmodels.PointStruct(
                        id=str(row.qdrant_point_id),
                        vector=vector,
                        payload=payload,
                    )
                )

            job = session.get(KnowledgeIngestionJob, job_id)
            if job is None:
                raise RuntimeError("ingestion job disappeared")
            job.document_id = document.id
            job.document_count = 1
            job.chunk_count = len(chunks)
            job.embedded_count = len(vectors)
            document_id = document.id

        self.qdrant_client.upsert(
            collection_name=self.qdrant_config.collection,
            points=points,
            wait=True,
        )

        with session_scope() as session:
            document = session.get(KnowledgeDocument, document_id)
            job = session.get(KnowledgeIngestionJob, job_id)
            if document is None or job is None:
                raise RuntimeError("ingestion persistence state disappeared")
            document.status = "ready"
            job.status = "succeeded"
            job.completed_at = datetime.now(UTC)
            for outbox_id in outbox_ids:
                event = session.get(KnowledgeSyncOutbox, outbox_id)
                if event is not None:
                    event.status = "succeeded"
                    event.attempt_count = 1
                    event.processed_at = datetime.now(UTC)

        return IngestionResult(
            object_key=parsed.source,
            status="succeeded",
            document_id=str(document_id),
            version=version,
            chunk_count=len(chunks),
        )

    @staticmethod
    def _payload(
        document: KnowledgeDocument,
        chunk: KnowledgeChunk,
        parsed: ParsedDocument,
    ) -> dict[str, Any]:
        metadata = parsed.metadata
        return {
            "chunk_id": str(chunk.id),
            "document_id": str(document.id),
            "text": chunk.text_content,
            "source": document.source,
            "title": document.title,
            "version": document.version,
            "language": document.language,
            "document_type": document.document_type,
            "active": True,
            "checksum": chunk.checksum,
            "applicable_plans": metadata.get("applicable_plans", []),
            "product_codes": metadata.get("product_codes", []),
            "region": metadata.get("region"),
            "valid_from": metadata.get("valid_from"),
            "valid_until": metadata.get("valid_until"),
            "metadata": metadata,
        }
