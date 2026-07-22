"""Postgres -> Qdrant outbox drain (RAG phase 4).

Originally planned for phase 6, but it is required as soon as Qdrant can be unavailable during
ingestion - which already happened: documents ingested while the collection did not exist are
now `status=ready` with their checksums recorded, so `knowledge-ingest` correctly reports them
UNCHANGED and will never retry the upsert. The outbox holds the only surviving intent, so
without this worker those vectors can never reach the index and dense retrieval has nothing to
search. Correctness, not a nicety.

Vectors are not stored in Postgres (the chunk text is), so a replay re-embeds the chunk. That is
deterministic and local: no quota, no network, no drift, and it doubles as a rebuild path if
Qdrant is ever wiped.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from knowledge_service.embeddings import get_embedder, get_sparse_embedder, hybrid_enabled
from knowledge_service.ingestion import qdrant_payload
from knowledge_service.qdrant_store import (
    DENSE_VECTOR_NAME,
    SPARSE_VECTOR_NAME,
    get_client,
    qdrant_collection,
)
from persistence.models.knowledge import KnowledgeChunk, KnowledgeDocument, KnowledgeSyncOutbox

logger = logging.getLogger(__name__)

BATCH_SIZE = 200
MAX_ATTEMPTS = 8
BACKOFF_CAP_SECONDS = 600


def backoff_seconds(attempt_count: int) -> int:
    """Exponential backoff, capped. Attempt 1 -> 2s, 2 -> 4s, ... never beyond the cap."""
    return min(BACKOFF_CAP_SECONDS, 2 ** max(1, min(attempt_count, 16)))


def _due(session: Session, limit: int) -> list[KnowledgeSyncOutbox]:
    """Claimable events: pending/failed, past their backoff, oldest first."""
    now = datetime.now(UTC)
    return list(
        session.scalars(
            select(KnowledgeSyncOutbox)
            .where(
                KnowledgeSyncOutbox.status.in_(("pending", "failed")),
                KnowledgeSyncOutbox.attempt_count < MAX_ATTEMPTS,
                KnowledgeSyncOutbox.available_at <= now,
            )
            .order_by(KnowledgeSyncOutbox.available_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    )


def _apply_upsert(session: Session, client, embedder, event: KnowledgeSyncOutbox) -> str:
    from qdrant_client.models import PointStruct, SparseVector

    chunk = session.get(KnowledgeChunk, event.aggregate_id)
    if chunk is None:
        return "orphan"  # chunk deleted after the event was queued: nothing to index
    if not chunk.active:
        return "inactive"  # superseded before we drained: the delete event covers it
    # The ORM declares no relationships on these models, so load the parent explicitly.
    document = session.get(KnowledgeDocument, chunk.document_id)
    if document is None:
        return "orphan"

    dense_vec = embedder.embed_passages([chunk.text_content])[0]
    if len(dense_vec) != chunk.embedding_dimensions:
        # The chunk was embedded by a different model than the one configured now. Indexing it
        # would mix incompatible vector spaces in one collection.
        raise RuntimeError(
            f"chunk {chunk.id} was embedded as {chunk.embedding_dimensions}d by "
            f"{chunk.embedding_model!r}; current model emits {len(dense_vec)}d - re-ingest instead"
        )
    vector = {DENSE_VECTOR_NAME: dense_vec}
    if hybrid_enabled():
        sparse = get_sparse_embedder().embed_passages([chunk.text_content])[0]
        vector[SPARSE_VECTOR_NAME] = SparseVector(
            indices=list(sparse.indices), values=list(sparse.values)
        )
    client.upsert(
        collection_name=qdrant_collection(),
        points=[
            PointStruct(
                id=str(chunk.qdrant_point_id),
                vector=vector,
                payload=qdrant_payload(document, chunk.text_content, chunk.ordinal),
            )
        ],
    )
    return "upserted"


def _apply_delete(client, event: KnowledgeSyncOutbox) -> str:
    point_id = (event.payload or {}).get("qdrant_point_id")
    if not point_id:
        return "orphan"
    client.delete(collection_name=qdrant_collection(), points_selector=[str(point_id)])
    return "deleted"


def drain(session: Session, limit: int = BATCH_SIZE) -> dict:
    """Process one batch of outbox events. Returns a counter dict."""
    client = get_client()
    embedder = get_embedder()
    counts = {"upserted": 0, "deleted": 0, "orphan": 0, "inactive": 0, "failed": 0}

    for event in _due(session, limit):
        try:
            if event.operation == "upsert":
                outcome = _apply_upsert(session, client, embedder, event)
            elif event.operation == "delete":
                outcome = _apply_delete(client, event)
            else:
                outcome = "orphan"
            event.status = "succeeded"
            event.processed_at = datetime.now(UTC)
            event.last_error = None
            counts[outcome] = counts.get(outcome, 0) + 1
        except Exception as exc:
            event.attempt_count += 1
            event.status = "failed"
            event.last_error = str(exc)[:2000]
            event.available_at = datetime.now(UTC) + timedelta(
                seconds=backoff_seconds(event.attempt_count)
            )
            counts["failed"] += 1
            logger.warning(
                "outbox %s attempt %d failed: %s", event.id, event.attempt_count, exc
            )
    session.commit()
    return counts


def run() -> None:
    """Console-script entrypoint: `knowledge-sync-outbox`. Drains until nothing is due."""
    logging.basicConfig(level=logging.INFO)
    from persistence.engine import session_scope

    total = {"upserted": 0, "deleted": 0, "orphan": 0, "inactive": 0, "failed": 0}
    with session_scope() as session:
        while True:
            counts = drain(session)
            for key, value in counts.items():
                total[key] = total.get(key, 0) + value
            if not any(counts.values()):
                break

    print(
        "UPSERTED={upserted} DELETED={deleted} ORPHAN={orphan} "
        "INACTIVE={inactive} FAILED={failed}".format(**total)
    )
    print("KNOWLEDGE_SYNC_OK" if total["failed"] == 0 else "KNOWLEDGE_SYNC_PARTIAL")
