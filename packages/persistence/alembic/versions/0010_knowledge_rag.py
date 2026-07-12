"""Knowledge RAG metadata and synchronization outbox.

Revision ID: 0010_knowledge_rag
Revises: 0009_auth_identity
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0010_knowledge_rag"
down_revision = "0009_auth_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS knowledge")

    op.create_table(
        "documents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("source", sa.String(500), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column(
            "language",
            sa.String(20),
            server_default=sa.text("'und'"),
            nullable=False,
        ),
        sa.Column(
            "document_type",
            sa.String(80),
            nullable=False,
        ),
        sa.Column(
            "checksum",
            sa.String(64),
            nullable=False,
        ),
        sa.Column(
            "version",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(20),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column(
            "minio_uri",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "language IN ('fr','ar','en','multilingual','und')",
            name="ck_documents_language",
        ),
        sa.CheckConstraint(
            "status IN "
            "('pending','processing','ready','failed','archived')",
            name="ck_documents_status",
        ),
        sa.CheckConstraint(
            "version > 0",
            name="ck_documents_positive_version",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name="pk_documents",
        ),
        sa.UniqueConstraint(
            "source",
            "version",
            name="uq_knowledge_documents_source_version",
        ),
        schema="knowledge",
    )
    op.create_index(
        "ix_knowledge_documents_status",
        "documents",
        ["status"],
        schema="knowledge",
    )
    op.create_index(
        "ix_knowledge_documents_checksum",
        "documents",
        ["checksum"],
        schema="knowledge",
    )

    op.create_table(
        "chunks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column(
            "qdrant_point_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "embedding_model",
            sa.String(160),
            nullable=False,
        ),
        sa.Column(
            "embedding_dimensions",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "ordinal >= 0",
            name="ck_chunks_nonnegative_ordinal",
        ),
        sa.CheckConstraint(
            "token_count > 0",
            name="ck_chunks_positive_token_count",
        ),
        sa.CheckConstraint(
            "embedding_dimensions > 0",
            name="ck_chunks_positive_embedding_dimensions",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["knowledge.documents.id"],
            name="fk_chunks_document_id_documents",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name="pk_chunks",
        ),
        sa.UniqueConstraint(
            "document_id",
            "ordinal",
            name="uq_knowledge_chunks_document_ordinal",
        ),
        sa.UniqueConstraint(
            "qdrant_point_id",
            name="uq_knowledge_chunks_qdrant_point_id",
        ),
        schema="knowledge",
    )
    op.create_index(
        "ix_knowledge_chunks_document_active",
        "chunks",
        ["document_id", "active"],
        schema="knowledge",
    )
    op.create_index(
        "ix_knowledge_chunks_checksum",
        "chunks",
        ["checksum"],
        schema="knowledge",
    )

    op.create_table(
        "ingestion_jobs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(20),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column(
            "source_object_key",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "document_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "chunk_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "embedded_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "embedding_model",
            sa.String(160),
            nullable=False,
        ),
        sa.Column(
            "embedding_dimensions",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "error_details",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN "
            "('pending','running','succeeded','failed','cancelled')",
            name="ck_ingestion_jobs_status",
        ),
        sa.CheckConstraint(
            "document_count >= 0",
            name="ck_ingestion_jobs_nonnegative_document_count",
        ),
        sa.CheckConstraint(
            "chunk_count >= 0",
            name="ck_ingestion_jobs_nonnegative_chunk_count",
        ),
        sa.CheckConstraint(
            "embedded_count >= 0",
            name="ck_ingestion_jobs_nonnegative_embedded_count",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["knowledge.documents.id"],
            name="fk_ingestion_jobs_document_id_documents",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name="pk_ingestion_jobs",
        ),
        schema="knowledge",
    )
    op.create_index(
        "ix_knowledge_ingestion_jobs_status_created",
        "ingestion_jobs",
        ["status", "created_at"],
        schema="knowledge",
    )

    op.create_table(
        "sync_outbox",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column(
            "aggregate_type",
            sa.String(40),
            server_default=sa.text("'chunk'"),
            nullable=False,
        ),
        sa.Column(
            "aggregate_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "operation",
            sa.String(20),
            nullable=False,
        ),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(20),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column(
            "attempt_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "last_error",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "operation IN ('upsert','delete')",
            name="ck_sync_outbox_operation",
        ),
        sa.CheckConstraint(
            "status IN "
            "('pending','processing','succeeded','failed')",
            name="ck_sync_outbox_status",
        ),
        sa.CheckConstraint(
            "attempt_count >= 0",
            name="ck_sync_outbox_nonnegative_attempt_count",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name="pk_sync_outbox",
        ),
        schema="knowledge",
    )
    op.create_index(
        "ix_knowledge_sync_outbox_dispatch",
        "sync_outbox",
        ["status", "available_at"],
        schema="knowledge",
    )
    op.create_index(
        "ix_knowledge_sync_outbox_aggregate",
        "sync_outbox",
        ["aggregate_type", "aggregate_id"],
        schema="knowledge",
    )

    op.execute(
        "CREATE TRIGGER trg_knowledge_documents_updated "
        "BEFORE UPDATE ON knowledge.documents "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
    )
    op.execute(
        "CREATE TRIGGER trg_knowledge_chunks_updated "
        "BEFORE UPDATE ON knowledge.chunks "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
    )
    op.execute(
        "CREATE TRIGGER trg_knowledge_ingestion_jobs_updated "
        "BEFORE UPDATE ON knowledge.ingestion_jobs "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
    )
    op.execute(
        "CREATE TRIGGER trg_knowledge_sync_outbox_updated "
        "BEFORE UPDATE ON knowledge.sync_outbox "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
    )


def downgrade() -> None:
    op.drop_table("sync_outbox", schema="knowledge")
    op.drop_table("ingestion_jobs", schema="knowledge")
    op.drop_table("chunks", schema="knowledge")
    op.drop_table("documents", schema="knowledge")
    op.execute("DROP SCHEMA IF EXISTS knowledge")
