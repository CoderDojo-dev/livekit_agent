"""Qdrant collection bootstrap + readiness (RAG phase 2).

The collection is the physical counterpart of `knowledge.chunks`: one point per chunk, whose
point id IS `knowledge.chunks.qdrant_point_id`, so Postgres stays the system of record and
Qdrant is a derived, rebuildable index.

Payload indexes exist for the fields Phase 5 filters on before vector scoring (`language`,
`document_type`, `source`, `active`). Creating them now means the ingestion in Phase 3 writes
into a collection that is already shaped correctly - no reindex later.

Bootstrap is idempotent: it creates what is missing and verifies what exists, so it is safe to
run on every deploy.
"""
from __future__ import annotations

import logging
import os

from knowledge_service.embeddings import embedding_dimensions

logger = logging.getLogger(__name__)

DEFAULT_COLLECTION = "telecom_knowledge"
DEFAULT_URL = "http://localhost:6333"

# Named vectors in the hybrid collection (RAG phase 8). The dense vector is the E5 bi-encoder
# embedding; the sparse vector is BM25 with an IDF modifier computed across the collection.
DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "bm25"

# Fields Phase 5 pre-filters on. Keyword for exact match, bool for the active flag.
PAYLOAD_INDEXES: dict[str, str] = {
    "language": "keyword",
    "document_type": "keyword",
    "source": "keyword",
    "active": "bool",
    # Phase 5 pre-filters. Indexed so Qdrant narrows the candidate set BEFORE vector scoring
    # rather than scanning every point and discarding afterwards.
    "applicable_plans": "keyword",
    "product_codes": "keyword",
    "region": "keyword",
}


class QdrantError(RuntimeError):
    """Qdrant is missing, unreachable, or misconfigured. Never degrade silently."""


def qdrant_url() -> str:
    return os.getenv("QDRANT_URL", DEFAULT_URL)


def qdrant_collection() -> str:
    return os.getenv("QDRANT_COLLECTION", DEFAULT_COLLECTION)


def qdrant_timeout() -> float:
    return float(os.getenv("QDRANT_TIMEOUT_S", "10"))


def get_client():
    """A configured Qdrant client. Raises QdrantError if the driver is absent."""
    try:
        from qdrant_client import QdrantClient
    except ImportError as exc:
        raise QdrantError(f"qdrant-client is not installed: {exc}") from exc
    return QdrantClient(url=qdrant_url(), timeout=qdrant_timeout())


def ensure_collection(client=None, collection: str | None = None) -> dict:
    """Create the collection + payload indexes if absent; verify them if present.

    Idempotent. Returns a small report describing the resulting collection. The collection uses
    NAMED vectors: a dense E5 vector + a sparse BM25 vector, so the hybrid retriever can query
    either (or fuse both via RRF).
    """
    from qdrant_client.models import (  # type: ignore[attr-defined]
        Distance,
        HnswConfigDiff,
        Modifier,
        SparseVectorParams,
        VectorParams,
    )

    client = client or get_client()
    name = collection or qdrant_collection()
    dimensions = embedding_dimensions()

    try:
        exists = client.collection_exists(collection_name=name)
    except Exception as exc:
        raise QdrantError(f"cannot reach Qdrant at {qdrant_url()}: {exc}") from exc

    if not exists:
        logger.info("creating Qdrant collection %s (%d dims, cosine + bm25 sparse)", name, dimensions)
        try:
            client.create_collection(
                collection_name=name,
                vectors_config={
                    DENSE_VECTOR_NAME: VectorParams(size=dimensions, distance=Distance.COSINE),
                },
                sparse_vectors_config={
                    # IDF modifier => Qdrant computes BM25 IDF weighting across the collection.
                    SPARSE_VECTOR_NAME: SparseVectorParams(modifier=Modifier.IDF),  # type: ignore[call-arg]
                },
                # m=16 / ef_construct=128 are Qdrant's balanced defaults: good recall at a
                # small corpus, and the graph stays cheap to build during ingestion.
                hnsw_config=HnswConfigDiff(m=16, ef_construct=128),
            )
        except Exception as exc:
            raise QdrantError(f"cannot create collection {name!r}: {exc}") from exc

    for field, schema in PAYLOAD_INDEXES.items():
        try:
            client.create_payload_index(
                collection_name=name,
                field_name=field,
                field_schema=schema,
            )
        except Exception as exc:  # already-exists is the common, benign case
            logger.debug("payload index %s on %s: %s", field, name, exc)

    return verify_collection(client=client, collection=name)


def verify_collection(client=None, collection: str | None = None) -> dict:
    """Assert the live collection matches the configured model. Raises QdrantError if not.

    This is the gate that stops a dimension/distance mismatch from being discovered later as
    silently bad retrieval.
    """
    client = client or get_client()
    name = collection or qdrant_collection()
    expected_dimensions = embedding_dimensions()

    try:
        info = client.get_collection(collection_name=name)
    except Exception as exc:
        raise QdrantError(f"collection {name!r} is missing or unreachable: {exc}") from exc

    params = info.config.params
    vectors = params.vectors
    # Named vectors: we expect a "dense" key (E5) and a "bm25" sparse vector. An unnamed single
    # vector means the collection was built by the old pipeline and must be recreated.
    if not isinstance(vectors, dict) or DENSE_VECTOR_NAME not in vectors:
        raise QdrantError(
            f"collection {name!r} must have a named '{DENSE_VECTOR_NAME}' vector; recreate it "
            f"with `knowledge-bootstrap-qdrant`"
        )
    dense = vectors[DENSE_VECTOR_NAME]
    size = int(dense.size)
    distance = str(dense.distance).split(".")[-1].lower()

    if size != expected_dimensions:
        raise QdrantError(
            f"collection {name!r} has {size} dimensions but the configured model "
            f"emits {expected_dimensions}; recreate the collection or fix EMBEDDING_MODEL"
        )
    if distance != "cosine":
        raise QdrantError(f"collection {name!r} uses {distance!r} distance; expected cosine")

    sparse = getattr(params, "sparse_vectors", None) or {}
    if SPARSE_VECTOR_NAME not in sparse:
        raise QdrantError(f"collection {name!r} is missing sparse vector {SPARSE_VECTOR_NAME!r}")

    try:
        schema = set(info.payload_schema or {})
    except Exception:
        schema = set()
    missing = sorted(set(PAYLOAD_INDEXES) - schema)

    return {
        "collection": name,
        "dimensions": size,
        "distance": distance,
        "points": int(info.points_count or 0),
        "missing_payload_indexes": missing,
    }


def bootstrap() -> None:
    """Console-script entrypoint: `knowledge-bootstrap-qdrant`."""
    logging.basicConfig(level=logging.INFO)
    report = ensure_collection()
    for key, value in report.items():
        print(f"{key}={value}")
    print("QDRANT_BOOTSTRAP_OK")
