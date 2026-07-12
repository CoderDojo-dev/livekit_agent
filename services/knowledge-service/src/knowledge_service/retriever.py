"""Filtered dense and hybrid retrieval over NVIDIA NIM, Qdrant, and Postgres."""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from qdrant_client import QdrantClient, models

from knowledge_service.embeddings import NIMEmbeddingClient
from knowledge_service.qdrant_store import QdrantConfig, verify_collection


class RetrievalError(RuntimeError):
    """Raised when retrieval cannot produce trustworthy grounded results."""


@dataclass(frozen=True, slots=True)
class SearchFilters:
    language: str | None = None
    document_type: str | None = None
    applicable_plans: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Passage:
    text: str
    source: str
    score: float
    language: str
    document_type: str
    metadata: dict[str, Any] = field(default_factory=dict)


class Retriever(Protocol):
    def search(
        self,
        query: str,
        top_k: int = 4,
        filters: SearchFilters | None = None,
    ) -> list[Passage]: ...


def build_qdrant_filter(filters: SearchFilters) -> models.Filter:
    must: list[models.Condition] = [
        models.FieldCondition(
            key="active",
            match=models.MatchValue(value=True),
        )
    ]
    if filters.language:
        must.append(
            models.FieldCondition(
                key="language",
                match=models.MatchValue(value=filters.language),
            )
        )
    if filters.document_type:
        must.append(
            models.FieldCondition(
                key="document_type",
                match=models.MatchValue(value=filters.document_type),
            )
        )
    if filters.applicable_plans:
        must.append(
            models.FieldCondition(
                key="applicable_plans",
                match=models.MatchAny(any=list(filters.applicable_plans)),
            )
        )
    return models.Filter(must=must)


class QdrantNIMRetriever:
    """Dense retrieval with metadata pre-filters applied before vector scoring."""

    def __init__(self, client: QdrantClient, collection: str, embedder: NIMEmbeddingClient) -> None:
        if not collection.strip():
            raise ValueError("collection is required")
        self.client = client
        self.collection = collection
        self.embedder = embedder

    def search(
        self,
        query: str,
        top_k: int = 4,
        filters: SearchFilters | None = None,
    ) -> list[Passage]:
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("query must not be empty")
        if not 1 <= top_k <= 100:
            raise ValueError("top_k must be between 1 and 100")
        effective_filters = filters or SearchFilters()
        vector = self.embedder.embed_query(normalized_query)
        try:
            hits = self.client.search(
                collection_name=self.collection,
                query_vector=vector,
                query_filter=build_qdrant_filter(effective_filters),
                limit=top_k,
                with_payload=True,
                with_vectors=False,
            )
        except Exception as exc:
            raise RetrievalError("Qdrant dense search failed") from exc
        return [self._passage_from_hit(hit) for hit in hits]

    @staticmethod
    def _passage_from_hit(hit: Any) -> Passage:
        payload = hit.payload
        if not isinstance(payload, Mapping):
            raise RetrievalError("Qdrant hit has no payload")
        text_value = str(payload.get("text") or "").strip()
        source = str(payload.get("source") or "").strip()
        if not text_value or not source:
            raise RetrievalError("Qdrant hit is missing passage text or citation source")
        reserved = {"text", "source", "language", "document_type"}
        return Passage(
            text=text_value,
            source=source,
            score=float(hit.score),
            language=str(payload.get("language") or "und"),
            document_type=str(payload.get("document_type") or "unknown"),
            metadata={str(k): v for k, v in payload.items() if k not in reserved},
        )

    def close(self) -> None:
        self.embedder.close()
        self.client.close()


class HybridRetriever:
    """Fuse dense Qdrant and sparse Postgres rankings using RRF."""

    def __init__(
        self,
        dense: QdrantNIMRetriever,
        sparse: Any,
        *,
        candidate_multiplier: int = 4,
        rank_constant: int = 60,
    ) -> None:
        if candidate_multiplier < 1:
            raise ValueError("candidate_multiplier must be positive")
        self.dense = dense
        self.sparse = sparse
        self.candidate_multiplier = candidate_multiplier
        self.rank_constant = rank_constant
        self.collection = dense.collection
        self.embedder = dense.embedder

    def search(
        self,
        query: str,
        top_k: int = 4,
        filters: SearchFilters | None = None,
    ) -> list[Passage]:
        from knowledge_service.hybrid import reciprocal_rank_fusion

        if not 1 <= top_k <= 20:
            raise ValueError("top_k must be between 1 and 20")
        effective_filters = filters or SearchFilters()
        candidate_k = min(top_k * self.candidate_multiplier, 100)
        dense = self.dense.search(query, candidate_k, effective_filters)
        sparse = self.sparse.search(query, candidate_k, effective_filters)
        return reciprocal_rank_fusion(
            dense,
            sparse,
            top_k=top_k,
            rank_constant=self.rank_constant,
        )

    def close(self) -> None:
        self.dense.close()


def get_retriever() -> HybridRetriever:
    """Build strict hybrid production retrieval; never downgrade to lexical-only."""
    import os

    from knowledge_service.hybrid import PostgresSparseRetriever
    from persistence.engine import get_sessionmaker

    config = QdrantConfig.from_env()
    client = config.client()
    embedder: NIMEmbeddingClient | None = None
    try:
        verify_collection(client, config)
        embedder = NIMEmbeddingClient.from_env()
        embedder.probe()
        dense = QdrantNIMRetriever(client, config.collection, embedder)
        sparse = PostgresSparseRetriever(get_sessionmaker())
        return HybridRetriever(
            dense,
            sparse,
            candidate_multiplier=int(os.getenv("HYBRID_CANDIDATE_MULTIPLIER", "4")),
            rank_constant=int(os.getenv("HYBRID_RRF_K", "60")),
        )
    except Exception:
        if embedder is not None:
            embedder.close()
        client.close()
        raise


_TOKEN = re.compile(r"[a-z0-9]+")


class LexicalRetriever:
    """Offline unit-test helper, never selected by the production factory."""

    def __init__(self, documents: Sequence[Any] | None = None) -> None:
        if documents is None:
            from knowledge_service.corpus import CORPUS

            documents = CORPUS
        self._documents = tuple(documents)

    def search(
        self,
        query: str,
        top_k: int = 4,
        filters: SearchFilters | None = None,
    ) -> list[Passage]:
        del filters
        terms = set(_TOKEN.findall(query.lower()))
        scored: list[Passage] = []
        for document in self._documents:
            document_terms = _TOKEN.findall(f"{document.title} {document.text}".lower())
            overlap = sum(term in terms for term in document_terms)
            if overlap:
                scored.append(
                    Passage(
                        text=document.text,
                        source=document.source,
                        score=overlap / max(len(document_terms) ** 0.5, 1),
                        language=getattr(document, "language", "und"),
                        document_type=getattr(document, "document_type", "offline"),
                    )
                )
        return sorted(scored, key=lambda item: item.score, reverse=True)[:top_k]
