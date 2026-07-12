"""Durable Postgres-to-Qdrant synchronization outbox worker."""
from __future__ import annotations

import argparse
import logging
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from qdrant_client import models
from sqlalchemy import select

from knowledge_service.qdrant_store import QdrantConfig, verify_collection
from persistence.engine import get_sessionmaker
from persistence.models.knowledge import KnowledgeSyncOutbox

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class OutboxWorkerConfig:
    batch_size: int = 50
    max_attempts: int = 5
    base_backoff_seconds: float = 2.0
    poll_seconds: float = 2.0

    @classmethod
    def from_env(cls) -> OutboxWorkerConfig:
        config = cls(
            batch_size=int(os.getenv("KNOWLEDGE_OUTBOX_BATCH_SIZE", "50")),
            max_attempts=int(os.getenv("KNOWLEDGE_OUTBOX_MAX_ATTEMPTS", "5")),
            base_backoff_seconds=float(
                os.getenv("KNOWLEDGE_OUTBOX_BACKOFF_S", "2")
            ),
            poll_seconds=float(os.getenv("KNOWLEDGE_OUTBOX_POLL_S", "2")),
        )
        if config.batch_size < 1 or config.max_attempts < 1:
            raise ValueError("outbox batch size and max attempts must be positive")
        if config.base_backoff_seconds < 0 or config.poll_seconds < 0:
            raise ValueError("outbox timing values cannot be negative")
        return config


class KnowledgeOutboxWorker:
    def __init__(
        self,
        *,
        session_factory,
        qdrant: Any,
        collection: str,
        config: OutboxWorkerConfig,
    ) -> None:
        self.session_factory = session_factory
        self.qdrant = qdrant
        self.collection = collection
        self.config = config

    def run_once(self) -> int:
        event_ids = self._claim()
        for event_id in event_ids:
            self._deliver(event_id)
        return len(event_ids)

    def _claim(self) -> list[Any]:
        now = datetime.now(UTC)
        with self.session_factory.begin() as session:
            rows = list(
                session.scalars(
                    select(KnowledgeSyncOutbox)
                    .where(
                        KnowledgeSyncOutbox.status.in_(["pending", "failed"]),
                        KnowledgeSyncOutbox.available_at <= now,
                        KnowledgeSyncOutbox.attempt_count < self.config.max_attempts,
                    )
                    .order_by(KnowledgeSyncOutbox.created_at)
                    .with_for_update(skip_locked=True)
                    .limit(self.config.batch_size)
                )
            )
            for row in rows:
                row.status = "processing"
            return [row.id for row in rows]

    def _deliver(self, event_id: Any) -> None:
        with self.session_factory() as session:
            event = session.get(KnowledgeSyncOutbox, event_id)
            if event is None or event.status != "processing":
                return
            operation = event.operation
            payload = dict(event.payload or {})

        try:
            point_id = str(payload["point_id"])
            if operation == "upsert":
                vector = payload.get("vector")
                point_payload = payload.get("payload")
                if not isinstance(vector, list) or not isinstance(point_payload, dict):
                    raise ValueError("outbox upsert payload is invalid")
                self.qdrant.upsert(
                    collection_name=self.collection,
                    points=[
                        models.PointStruct(
                            id=point_id,
                            vector=vector,
                            payload=point_payload,
                        )
                    ],
                    wait=True,
                )
            elif operation == "delete":
                self.qdrant.delete(
                    collection_name=self.collection,
                    points_selector=models.PointIdsList(points=[point_id]),
                    wait=True,
                )
            else:
                raise ValueError(f"unsupported outbox operation: {operation}")
        except Exception as exc:
            self._mark_failure(event_id, exc)
            return

        with self.session_factory.begin() as session:
            event = session.get(KnowledgeSyncOutbox, event_id)
            if event is not None:
                event.status = "succeeded"
                event.attempt_count += 1
                event.processed_at = datetime.now(UTC)
                event.last_error = None

    def _mark_failure(self, event_id: Any, exc: Exception) -> None:
        with self.session_factory.begin() as session:
            event = session.get(KnowledgeSyncOutbox, event_id)
            if event is None:
                return
            event.attempt_count += 1
            event.status = "failed"
            delay = self.config.base_backoff_seconds * (
                2 ** max(event.attempt_count - 1, 0)
            )
            event.available_at = datetime.now(UTC) + timedelta(seconds=delay)
            event.last_error = str(exc)[:4000]
            if event.attempt_count >= self.config.max_attempts:
                logger.error("outbox event %s exhausted retries: %s", event.id, exc)
            else:
                logger.warning("outbox event %s will retry: %s", event.id, exc)


def build_worker() -> KnowledgeOutboxWorker:
    qdrant_config = QdrantConfig.from_env()
    qdrant = qdrant_config.client()
    verify_collection(qdrant, qdrant_config)
    return KnowledgeOutboxWorker(
        session_factory=get_sessionmaker(),
        qdrant=qdrant,
        collection=qdrant_config.collection,
        config=OutboxWorkerConfig.from_env(),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Process knowledge Qdrant outbox")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    worker = build_worker()
    try:
        while True:
            processed = worker.run_once()
            print(f"KNOWLEDGE_OUTBOX_PROCESSED={processed}", flush=True)
            if args.once:
                break
            if processed == 0:
                time.sleep(worker.config.poll_seconds)
    finally:
        worker.qdrant.close()


if __name__ == "__main__":
    main()
