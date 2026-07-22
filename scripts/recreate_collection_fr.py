"""Drop the Qdrant collection and recreate it with named vectors (dense + bm25 sparse).

Phase 8 requires a collection with NAMED vectors (`dense` = 384d cosine, `bm25` = sparse IDF).
The old collection (pre-Phase 8) has an unnamed single vector — incompatible. This script:

  1. Drops the existing collection (all vectors are lost — they will be rebuilt from Postgres).
  2. Creates a fresh one with `ensure_collection()` (named vectors + payload indexes).
  3. Drains the outbox so every chunk in Postgres gets re-embedded and re-indexed.

Usage:
    python scripts/recreate_collection_fr.py

WARNING: all vectors in Qdrant are deleted. Postgres chunks are the system of record and survive.
"""
from __future__ import annotations

import logging
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    from knowledge_service.embeddings import get_embedder, get_sparse_embedder, hybrid_enabled
    from knowledge_service.qdrant_store import (
        QdrantError,
        ensure_collection,
        get_client,
        qdrant_collection,
    )

    name = qdrant_collection()
    client = get_client()

    # 1. Drop existing collection
    try:
        if client.collection_exists(collection_name=name):
            print(f"Dropping collection {name!r}...")
            client.delete_collection(collection_name=name)
            print("  dropped.")
        else:
            print(f"Collection {name!r} does not exist yet.")
    except Exception as exc:
        print(f"ERROR: cannot drop collection {name!r}: {exc}", file=sys.stderr)
        sys.exit(1)

    # 2. Create fresh collection with named vectors
    print(f"Creating collection {name!r} (dense + bm25 sparse)...")
    try:
        report = ensure_collection(client=client, collection=name)
        print(f"  created: {report}")
    except QdrantError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    # 3. Warm models (so the outbox drain does not pay model-load on the first chunk)
    print("Warming dense embedder...")
    get_embedder().health_check()
    print("  ok")
    if hybrid_enabled():
        print("Warming sparse embedder...")
        get_sparse_embedder().health_check()
        print("  ok")

    # 4. Drain the outbox — every ready chunk in Postgres gets re-embedded and upserted
    from knowledge_service.sync_worker import drain

    from persistence.engine import session_scope

    print("Draining outbox...")
    total = {"upserted": 0, "deleted": 0, "orphan": 0, "inactive": 0, "failed": 0}
    with session_scope() as session:
        while True:
            counts = drain(session, limit=200)
            for key, value in counts.items():
                total[key] = total.get(key, 0) + value
            if not any(counts.values()):
                break
    print(
        f"  UPSERTED={total['upserted']} DELETED={total['deleted']} "
        f"ORPHAN={total['orphan']} INACTIVE={total['inactive']} FAILED={total['failed']}"
    )
    if total["failed"] > 0:
        print("WARNING: some outbox events failed. Check logs and re-run.", file=sys.stderr)
        sys.exit(1)

    # 5. Verify
    from knowledge_service.qdrant_store import verify_collection

    report = verify_collection(client=client, collection=name)
    print(f"\nCollection ready: {report}")
    print("RECREATE_COLLECTION_OK")


if __name__ == "__main__":
    main()
