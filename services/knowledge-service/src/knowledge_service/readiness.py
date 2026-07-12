"""Fail-closed production readiness gates for knowledge retrieval."""
from __future__ import annotations

from dataclasses import dataclass

from qdrant_client import QdrantClient
from sqlalchemy import text

from knowledge_service.embeddings import NIMEmbeddingClient
from knowledge_service.qdrant_store import QdrantConfig, verify_collection


class ProductionReadinessError(RuntimeError):
    """Raised when production retrieval dependencies are incomplete."""


@dataclass(frozen=True, slots=True)
class ReadinessReport:
    qdrant_points: int
    postgres_active_chunks: int
    dimensions: int


def verify_production_readiness(
    *,
    qdrant: QdrantClient,
    qdrant_config: QdrantConfig,
    embedder: NIMEmbeddingClient,
    session_factory,
) -> ReadinessReport:
    """Raise unless NIM, non-empty Qdrant, and indexed Postgres FTS are ready."""
    verify_collection(qdrant, qdrant_config)
    embedder.probe()

    count_result = qdrant.count(
        collection_name=qdrant_config.collection,
        exact=True,
    )
    qdrant_points = int(count_result.count)
    if qdrant_points < 1:
        raise ProductionReadinessError(
            f"Qdrant collection {qdrant_config.collection!r} is empty"
        )

    with session_factory() as session:
        fts_type = session.scalar(
            text(
                """
                SELECT data_type
                FROM information_schema.columns
                WHERE table_schema = 'knowledge'
                  AND table_name = 'chunks'
                  AND column_name = 'search_vector'
                """
            )
        )
        if fts_type != "tsvector":
            raise ProductionReadinessError(
                "knowledge.chunks.search_vector is missing; apply 0011_knowledge_fts"
            )
        active_chunks = int(
            session.scalar(
                text(
                    """
                    SELECT count(*)
                    FROM knowledge.chunks AS c
                    JOIN knowledge.documents AS d ON d.id = c.document_id
                    WHERE c.active IS TRUE
                      AND d.status = 'ready'
                      AND c.search_vector IS NOT NULL
                    """
                )
            )
            or 0
        )
    if active_chunks < 1:
        raise ProductionReadinessError("Postgres has no active searchable chunks")

    return ReadinessReport(
        qdrant_points=qdrant_points,
        postgres_active_chunks=active_chunks,
        dimensions=embedder.config.dimensions,
    )
