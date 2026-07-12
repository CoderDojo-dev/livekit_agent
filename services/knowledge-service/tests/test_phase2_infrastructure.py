"""Offline contract tests for Phase 2 RAG infrastructure."""
from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
from qdrant_client import models

from knowledge_service.embeddings import (
    EmbeddingInputType,
    NIMEmbeddingClient,
    NIMEmbeddingConfig,
    NIMEmbeddingError,
)
from knowledge_service.qdrant_store import (
    PAYLOAD_INDEXES,
    QdrantCollectionError,
    QdrantConfig,
    bootstrap_collection,
    verify_collection,
)


def _nim_config(**overrides: object) -> NIMEmbeddingConfig:
    values = {
        "api_key": "test-key",
        "dimensions": 384,
        "max_attempts": 3,
        "backoff_seconds": 0.01,
    }
    values.update(overrides)
    return NIMEmbeddingConfig(**values)


def test_nim_client_sends_input_type_and_validates_384_dimensions() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(__import__("json").loads(request.content))
        return httpx.Response(
            200,
            json={"data": [{"index": 0, "embedding": [0.1] * 384}]},
        )

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as http_client:
        client = NIMEmbeddingClient(_nim_config(), client=http_client)
        vector = client.embed(["bonjour"], input_type=EmbeddingInputType.PASSAGE)[0]

    assert len(vector) == 384
    assert captured["input_type"] == "passage"
    assert captured["dimensions"] == 384
    assert captured["model"] == "nvidia/llama-nemotron-embed-1b-v2"


def test_nim_client_retries_transient_failures_with_backoff() -> None:
    calls = 0
    sleeps: list[float] = []

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls < 3:
            return httpx.Response(503, text="temporarily unavailable")
        return httpx.Response(200, json={"data": [{"embedding": [0.2] * 384}]})

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = NIMEmbeddingClient(
            _nim_config(),
            client=http_client,
            sleep=sleeps.append,
        )
        vector = client.embed_query("forfait mobile")

    assert len(vector) == 384
    assert calls == 3
    assert sleeps == [0.01, 0.02]


def test_nim_client_rejects_wrong_dimension_response() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"embedding": [0.1] * 383}]})

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = NIMEmbeddingClient(
            _nim_config(max_attempts=1),
            client=http_client,
        )
        with pytest.raises(NIMEmbeddingError, match="failed after 1 attempts"):
            client.embed_query("invalid vector")


class FakeQdrantClient:
    def __init__(self, *, exists: bool = False, size: int = 384) -> None:
        self.exists = exists
        self.size = size
        self.distance = models.Distance.COSINE
        self.created: dict | None = None
        self.indexes: list[tuple[str, models.PayloadSchemaType]] = []

    def collection_exists(self, _: str) -> bool:
        return self.exists

    def create_collection(self, **kwargs: object) -> None:
        self.created = kwargs
        vectors = kwargs["vectors_config"]
        self.size = vectors.size
        self.distance = vectors.distance
        self.exists = True

    def get_collection(self, _: str) -> SimpleNamespace:
        vectors = SimpleNamespace(size=self.size, distance=self.distance)
        return SimpleNamespace(
            config=SimpleNamespace(params=SimpleNamespace(vectors=vectors))
        )

    def create_payload_index(self, **kwargs: object) -> None:
        self.indexes.append((kwargs["field_name"], kwargs["field_schema"]))


def test_qdrant_bootstrap_creates_cosine_collection_and_payload_indexes() -> None:
    client = FakeQdrantClient()
    config = QdrantConfig()

    created = bootstrap_collection(client, config)

    assert created is True
    assert client.created is not None
    vectors = client.created["vectors_config"]
    assert vectors.size == 384
    assert vectors.distance == models.Distance.COSINE
    assert dict(client.indexes) == PAYLOAD_INDEXES


def test_qdrant_readiness_rejects_wrong_vector_size() -> None:
    client = FakeQdrantClient(exists=True, size=1536)

    with pytest.raises(QdrantCollectionError, match="expected 384"):
        verify_collection(client, QdrantConfig())
