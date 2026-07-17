"""Corpus lifecycle: see what is indexed, and remove what should not be (RAG phase 6a).

Ingestion could add documents but nothing could ever remove one. A single mistaken upload was
permanent, and it does not sit quietly: an unrelated file still gets embedded, still scores ~0.8
against every question (E5's low-temperature training compresses cosine into ~0.7-1.0), and
still outranks real procedures. A corpus you cannot curate degrades with every mistake.

Purge is a full removal across all three stores, in the order that cannot strand data:
  1. Postgres  - deactivate chunks, archive documents  (the system of record)
  2. Outbox    - queue the deletes                     (so a Qdrant outage still converges)
  3. Qdrant    - drop the points now                   (best-effort; the outbox is the fallback)
  4. MinIO     - remove the object                     (or the next bucket scan re-ingests it)

Deleting the object matters: an archived document no longer matches the `status='ready'`
checksum guard, so leaving the file in the bucket would re-ingest it as a new version on the
next `knowledge-ingest`.
"""
from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from knowledge_service.qdrant_store import get_client, qdrant_collection
from persistence.models.knowledge import KnowledgeChunk, KnowledgeDocument, KnowledgeSyncOutbox

logger = logging.getLogger(__name__)


def list_documents(session: Session) -> list[dict]:
    """Every document in the corpus with its live chunk count, newest source first."""
    live_chunks = (
        select(
            KnowledgeChunk.document_id.label("document_id"),
            func.count().label("chunks"),
        )
        .where(KnowledgeChunk.active.is_(True))
        .group_by(KnowledgeChunk.document_id)
        .subquery()
    )
    rows = session.execute(
        select(KnowledgeDocument, func.coalesce(live_chunks.c.chunks, 0))
        .outerjoin(live_chunks, live_chunks.c.document_id == KnowledgeDocument.id)
        .order_by(KnowledgeDocument.source.asc(), KnowledgeDocument.version.desc())
    ).all()
    return [
        {
            "document_id": str(document.id),
            "source": document.source,
            "title": document.title,
            "language": document.language,
            "document_type": document.document_type,
            "version": document.version,
            "status": document.status,
            "chunks": int(chunks or 0),
            "checksum": document.checksum,
        }
        for document, chunks in rows
    ]


def purge_document(session: Session, source: str, remove_object: bool = True) -> dict:
    """Remove ``source`` from the index, the records, and the bucket.

    Raises LookupError when the source is unknown, so the API can answer 404 instead of
    reporting a successful deletion of nothing.
    """
    documents = list(
        session.scalars(select(KnowledgeDocument).where(KnowledgeDocument.source == source))
    )
    if not documents:
        raise LookupError(f"no document with source {source!r}")

    point_ids: list[str] = []
    for document in documents:
        chunks = session.scalars(
            select(KnowledgeChunk).where(
                KnowledgeChunk.document_id == document.id, KnowledgeChunk.active.is_(True)
            )
        )
        for chunk in chunks:
            chunk.active = False
            point_ids.append(str(chunk.qdrant_point_id))
            session.add(
                KnowledgeSyncOutbox(
                    aggregate_type="chunk",
                    aggregate_id=chunk.id,
                    operation="delete",
                    payload={"qdrant_point_id": str(chunk.qdrant_point_id)},
                )
            )
        document.status = "archived"

    removed_points = 0
    if point_ids:
        try:
            get_client().delete(
                collection_name=qdrant_collection(), points_selector=point_ids
            )
            removed_points = len(point_ids)
        except Exception as exc:  # the outbox already holds the intent
            logger.error("qdrant delete failed (outbox will replay): %s", exc)

    object_removed = False
    if remove_object:
        from knowledge_service.minio_store import KnowledgeStoreError, get_knowledge_store

        try:
            get_knowledge_store().delete(source)
            object_removed = True
        except KnowledgeStoreError as exc:
            # Leave a loud trail: the file will otherwise be re-ingested on the next bucket scan.
            logger.error("bucket object %s not removed: %s", source, exc)

    return {
        "source": source,
        "documents_archived": len(documents),
        "chunks_deactivated": len(point_ids),
        "points_removed": removed_points,
        "object_removed": object_removed,
    }
