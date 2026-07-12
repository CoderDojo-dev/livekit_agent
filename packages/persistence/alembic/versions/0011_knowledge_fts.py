"""PostgreSQL full-text index for hybrid knowledge retrieval.

Revision ID: 0011_knowledge_fts
Revises: 0010_knowledge_rag
"""
from alembic import op

revision = "0011_knowledge_fts"
down_revision = "0010_knowledge_rag"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE knowledge.chunks
        ADD COLUMN search_vector tsvector
        GENERATED ALWAYS AS (
            to_tsvector('simple', coalesce(text, ''))
        ) STORED
        """
    )
    op.execute(
        """
        CREATE INDEX ix_knowledge_chunks_search_vector_gin
        ON knowledge.chunks
        USING gin (search_vector)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS knowledge.ix_knowledge_chunks_search_vector_gin")
    op.execute("ALTER TABLE knowledge.chunks DROP COLUMN IF EXISTS search_vector")
