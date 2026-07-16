"""Rebuild the Qdrant index from Postgres (RAG phase 5b).

Qdrant is a derived index; Postgres is the system of record. Until now there was no path back:
once a document is `status=ready` with its checksum stored, `knowledge-ingest` reports UNCHANGED,
and once its outbox events are `succeeded`, `knowledge-sync-outbox` skips them. So a wiped,
corrupted, or partially-lost collection could never be restored - the vectors existed nowhere,
because vectors are not stored in Postgres, only `chunks.text_content` is.

That is exactly recoverable: re-embedding is deterministic, local, and free (no quota, no
network), so the index can always be rebuilt from the text. This is the recovery path, and it is
also how you migrate the corpus to a different embedding model - rebuild instead of re-download.
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from knowledge_service.embeddings import get_embedder
from knowledge_service.ingestion import qdrant_payload
from knowledge_service.qdrant_store import ensure_collection, get_client, qdrant_collection
from persistence.models.knowledge import KnowledgeChunk, KnowledgeDocument

logger = logging.getLogger(__name__)

BATCH_SIZE = 64


def _live_chunks(session: Session):
    """Every chunk that should be searchable: active, belonging to a ready document."""
    stmt = (
        select(KnowledgeChunk, KnowledgeDocument)
        .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
        .where(KnowledgeChunk.active.is_(True), KnowledgeDocument.status == "ready")
        .order_by(KnowledgeChunk.document_id, KnowledgeChunk.ordinal)
    )
    return session.execute(stmt).all()


def reindex(session: Session, recreate: bool = False) -> dict:
    """Re-embed and upsert every live chunk. Returns a counter dict.

    ``recreate`` drops the collection first: required when the configured embedding model no
    longer matches the collection's width, since two vector spaces cannot share a collection.
    """
    from qdrant_client.models import PointStruct

    client = get_client()
    embedder = get_embedder()
    collection = qdrant_collection()

    if recreate:
        try:
            client.delete_collection(collection_name=collection)
            logger.warning("dropped collection %s for a clean rebuild", collection)
        except Exception as exc:
            logger.info("delete_collection skipped (%s)", exc)
    ensure_collection(client=client, collection=collection)

    rows = _live_chunks(session)
    counts = {"indexed": 0, "skipped": 0, "documents": len({r[0].document_id for r in rows})}

    for start in range(0, len(rows), BATCH_SIZE):
        batch = rows[start : start + BATCH_SIZE]
        # Chunks embedded by a different model cannot share this collection's vector space.
        usable = [
            (chunk, document)
            for chunk, document in batch
            if chunk.embedding_dimensions == embedder.dimensions
        ]
        counts["skipped"] += len(batch) - len(usable)
        if not usable:
            continue

        vectors = embedder.embed_passages([chunk.text_content for chunk, _ in usable])
        client.upsert(
            collection_name=collection,
            points=[
                PointStruct(
                    id=str(chunk.qdrant_point_id),
                    vector=vector,
                    payload=qdrant_payload(document, chunk.text_content, chunk.ordinal),
                )
                for (chunk, document), vector in zip(usable, vectors)
            ],
        )
        counts["indexed"] += len(usable)
        logger.info("reindexed %d/%d chunks", counts["indexed"], len(rows))

    return counts


def run() -> None:
    """Console-script entrypoint: `knowledge-reindex [--recreate]`."""
    import sys

    logging.basicConfig(level=logging.INFO)
    from persistence.engine import session_scope

    recreate = "--recreate" in sys.argv
    with session_scope() as session:
        counts = reindex(session, recreate=recreate)

    client = get_client()
    points = int(client.get_collection(collection_name=qdrant_collection()).points_count or 0)
    print(
        f"DOCUMENTS={counts['documents']} INDEXED={counts['indexed']} "
        f"SKIPPED={counts['skipped']} POINTS_IN_COLLECTION={points}"
    )
    print("KNOWLEDGE_REINDEX_OK" if counts["skipped"] == 0 else "KNOWLEDGE_REINDEX_PARTIAL")
