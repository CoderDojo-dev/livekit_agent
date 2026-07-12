"""Knowledge RAG persistence.

PostgreSQL stores document, chunk, ingestion, and synchronization truth.
MinIO stores source files. Qdrant stores derived searchable vectors.
"""
from __future__ import annotations

import datetime
import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from persistence.base import Base, Timestamps, UUIDPrimaryKey


class KnowledgeDocument(UUIDPrimaryKey, Timestamps, Base):
    """Versioned source document stored in MinIO."""

    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(
            "language IN ('fr','ar','en','multilingual','und')",
            name="language",
        ),
        CheckConstraint(
            "status IN "
            "('pending','processing','ready','failed','archived')",
            name="status",
        ),
        CheckConstraint("version > 0", name="positive_version"),
        UniqueConstraint(
            "source",
            "version",
            name="uq_knowledge_documents_source_version",
        ),
        Index(
            "ix_knowledge_documents_status",
            "status",
        ),
        Index(
            "ix_knowledge_documents_checksum",
            "checksum",
        ),
        {"schema": "knowledge"},
    )

    source: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
    )
    language: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'und'"),
    )
    document_type: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
    )
    checksum: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("1"),
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'pending'"),
    )
    minio_uri: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    metadata_json: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )


class KnowledgeChunk(UUIDPrimaryKey, Timestamps, Base):
    """Normalized chunk whose UUID is also its Qdrant point ID."""

    __tablename__ = "chunks"
    __table_args__ = (
        CheckConstraint("ordinal >= 0", name="nonnegative_ordinal"),
        CheckConstraint("token_count > 0", name="positive_token_count"),
        CheckConstraint(
            "embedding_dimensions > 0",
            name="positive_embedding_dimensions",
        ),
        UniqueConstraint(
            "document_id",
            "ordinal",
            name="uq_knowledge_chunks_document_ordinal",
        ),
        UniqueConstraint(
            "qdrant_point_id",
            name="uq_knowledge_chunks_qdrant_point_id",
        ),
        Index(
            "ix_knowledge_chunks_document_active",
            "document_id",
            "active",
        ),
        Index(
            "ix_knowledge_chunks_checksum",
            "checksum",
        ),
        {"schema": "knowledge"},
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "knowledge.documents.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    ordinal: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    text_content: Mapped[str] = mapped_column(
        "text",
        Text,
        nullable=False,
    )
    token_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    checksum: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    qdrant_point_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    embedding_model: Mapped[str] = mapped_column(
        String(160),
        nullable=False,
    )
    embedding_dimensions: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    metadata_json: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )


class KnowledgeIngestionJob(UUIDPrimaryKey, Timestamps, Base):
    """Auditable execution record for one ingestion attempt."""

    __tablename__ = "ingestion_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN "
            "('pending','running','succeeded','failed','cancelled')",
            name="status",
        ),
        CheckConstraint(
            "document_count >= 0",
            name="nonnegative_document_count",
        ),
        CheckConstraint(
            "chunk_count >= 0",
            name="nonnegative_chunk_count",
        ),
        CheckConstraint(
            "embedded_count >= 0",
            name="nonnegative_embedded_count",
        ),
        Index(
            "ix_knowledge_ingestion_jobs_status_created",
            "status",
            "created_at",
        ),
        {"schema": "knowledge"},
    )

    document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "knowledge.documents.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'pending'"),
    )
    source_object_key: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    document_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    chunk_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    embedded_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    embedding_model: Mapped[str] = mapped_column(
        String(160),
        nullable=False,
    )
    embedding_dimensions: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    error_details: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    started_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class KnowledgeSyncOutbox(UUIDPrimaryKey, Timestamps, Base):
    """Durable Postgres-to-Qdrant synchronization event."""

    __tablename__ = "sync_outbox"
    __table_args__ = (
        CheckConstraint(
            "operation IN ('upsert','delete')",
            name="operation",
        ),
        CheckConstraint(
            "status IN ('pending','processing','succeeded','failed')",
            name="status",
        ),
        CheckConstraint(
            "attempt_count >= 0",
            name="nonnegative_attempt_count",
        ),
        Index(
            "ix_knowledge_sync_outbox_dispatch",
            "status",
            "available_at",
        ),
        Index(
            "ix_knowledge_sync_outbox_aggregate",
            "aggregate_type",
            "aggregate_id",
        ),
        {"schema": "knowledge"},
    )

    aggregate_type: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        server_default=text("'chunk'"),
    )
    aggregate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    operation: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    payload: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'pending'"),
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    available_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    processed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
