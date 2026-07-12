"""Offline contract tests for the production dense retriever."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from knowledge_service.retriever import QdrantNIMRetriever, RetrievalError


class FakeEmbedder:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def embed_query(self, query: str) -> list[float]:
        self.queries.append(query)
        return [0.1] * 384

    def close(self) -> None:
        return None


class FakeQdrant:
    def __init__(self, hits: list[SimpleNamespace]) -> None:
        self.hits = hits
        self.calls: list[dict] = []

    def search(self, **kwargs):
        self.calls.append(kwargs)
        return self.hits

    def close(self) -> None:
        return None


def test_dense_retriever_embeds_as_query_and_returns_citation_contract() -> None:
    hit = SimpleNamespace(
        score=0.91,
        payload={
            "text": "L'offre Flexi est un forfait postpayé.",
            "source": "validation/flexi.md",
            "language": "fr",
            "document_type": "product",
            "title": "Offre Flexi",
            "version": 1,
            "active": True,
        },
    )
    qdrant = FakeQdrant([hit])
    embedder = FakeEmbedder()
    retriever = QdrantNIMRetriever(qdrant, "telecom_knowledge", embedder)

    passages = retriever.search("Quel forfait postpayé est disponible ?", top_k=3)

    assert embedder.queries == ["Quel forfait postpayé est disponible ?"]
    assert len(passages) == 1
    assert passages[0].source == "validation/flexi.md"
    assert passages[0].language == "fr"
    assert passages[0].document_type == "product"
    assert passages[0].metadata["title"] == "Offre Flexi"
    assert qdrant.calls[0]["collection_name"] == "telecom_knowledge"
    assert qdrant.calls[0]["limit"] == 3
    assert qdrant.calls[0]["with_payload"] is True
    assert qdrant.calls[0]["query_filter"] is not None


def test_dense_retriever_rejects_uncitable_hits() -> None:
    qdrant = FakeQdrant([SimpleNamespace(score=0.5, payload={"text": "orphan"})])
    retriever = QdrantNIMRetriever(qdrant, "telecom_knowledge", FakeEmbedder())

    with pytest.raises(RetrievalError, match="citation source"):
        retriever.search("query")


def test_dense_retriever_validates_query_and_limit() -> None:
    retriever = QdrantNIMRetriever(FakeQdrant([]), "telecom_knowledge", FakeEmbedder())

    with pytest.raises(ValueError, match="empty"):
        retriever.search("   ")
    with pytest.raises(ValueError, match="between 1 and 20"):
        retriever.search("query", top_k=21)
