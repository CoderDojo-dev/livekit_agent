"""Strict dense retrieval over NVIDIA NIM embeddings and Qdrant."""
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
class Passage:
    """A scored passage with a complete citation contract."""

    text: str
    source: str
    score: float
    language: str
    document_type: str
    metadata: dict[str, Any] = field(default_factory=dict)


class Retriever(Protocol):
    def search(self, query: str, top_k: int = 4) -> list[Passage]: ...


class QdrantNIMRetriever:
    """Embed queries as `query`, search active Qdrant passages, return citations."""

    def __init__(
        self,
        client: QdrantClient,
        collection: str,
        embedder: NIMEmbeddingClient,
    ) -> None:
        if not collection.strip():
            raise ValueError("collection is required")
        self.client = client
        self.collection = collection
        self.embedder = embedder

    def search(self, query: str, top_k: int = 4) -> list[Passage]:
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("query must not be empty")
        if not 1 <= top_k <= 20:
            raise ValueError("top_k must be between 1 and 20")

        vector = self.embedder.embed_query(normalized_query)
        try:
            hits = self.client.search(
                collection_name=self.collection,
                query_vector=vector,
                query_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="active",
                            match=models.MatchValue(value=True),
                        )
                    ]
                ),
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

        text = str(payload.get("text") or "").strip()
        source = str(payload.get("source") or "").strip()
        language = str(payload.get("language") or "und").strip()
        document_type = str(payload.get("document_type") or "unknown").strip()
        if not text or not source:
            raise RetrievalError("Qdrant hit is missing passage text or citation source")

        reserved = {"text", "source", "language", "document_type"}
        metadata = {
            str(key): value
            for key, value in payload.items()
            if key not in reserved
        }
        return Passage(
            text=text,
            source=source,
            score=float(hit.score),
            language=language,
            document_type=document_type,
            metadata=metadata,
        )

    def close(self) -> None:
        self.embedder.close()
        self.client.close()


def get_retriever() -> QdrantNIMRetriever:
    """Build the production retriever or raise. There is no lexical downgrade."""
    config = QdrantConfig.from_env()
    client = config.client()
    embedder: NIMEmbeddingClient | None = None
    try:
        verify_collection(client, config)
        embedder = NIMEmbeddingClient.from_env()
        embedder.probe()
        return QdrantNIMRetriever(client, config.collection, embedder)
    except Exception:
        if embedder is not None:
            embedder.close()
        client.close()
        raise


# Offline-only helper retained for deterministic unit tests. Production never calls it.
_TOKEN = re.compile(r"[a-z0-9]+")


class LexicalRetriever:
    """Tiny offline test helper. Forbidden as a production fallback."""

    def __init__(self, documents: Sequence[Any] | None = None) -> None:
        if documents is None:
            from knowledge_service.corpus import CORPUS

            documents = CORPUS
        self._documents = tuple(documents)

    def search(self, query: str, top_k: int = 4) -> list[Passage]:
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
                        metadata={},
                    )
                )
        return sorted(scored, key=lambda item: item.score, reverse=True)[:top_k]
