"""Strict NVIDIA NIM embedding client for the knowledge pipeline."""
from __future__ import annotations

import math
import os
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import httpx

REQUIRED_EMBEDDING_DIMENSIONS = 384
_TRANSIENT_STATUS_CODES = {408, 429, 500, 502, 503, 504}


class EmbeddingInputType(StrEnum):
    """NVIDIA retrieval embedding modes."""

    QUERY = "query"
    PASSAGE = "passage"


class NIMEmbeddingError(RuntimeError):
    """Raised when NVIDIA NIM cannot return verified embeddings."""


@dataclass(frozen=True, slots=True)
class NIMEmbeddingConfig:
    """Validated NVIDIA NIM embedding configuration."""

    api_key: str
    model: str = "nvidia/llama-nemotron-embed-1b-v2"
    base_url: str = "https://integrate.api.nvidia.com/v1"
    dimensions: int = REQUIRED_EMBEDDING_DIMENSIONS
    timeout_seconds: float = 45.0
    max_attempts: int = 3
    backoff_seconds: float = 0.5

    @classmethod
    def from_env(cls) -> NIMEmbeddingConfig:
        api_key = os.getenv("NVIDIA_API_KEY", "").strip()
        if not api_key:
            raise NIMEmbeddingError("NVIDIA_API_KEY is required")

        config = cls(
            api_key=api_key,
            model=os.getenv(
                "NVIDIA_EMBEDDING_MODEL",
                "nvidia/llama-nemotron-embed-1b-v2",
            ).strip(),
            base_url=os.getenv(
                "NVIDIA_EMBEDDING_BASE_URL",
                "https://integrate.api.nvidia.com/v1",
            ).strip().rstrip("/"),
            dimensions=int(os.getenv("EMBEDDING_DIMENSIONS", "384")),
            timeout_seconds=float(os.getenv("NVIDIA_EMBEDDING_TIMEOUT_S", "45")),
            max_attempts=int(os.getenv("NVIDIA_EMBEDDING_MAX_ATTEMPTS", "3")),
            backoff_seconds=float(os.getenv("NVIDIA_EMBEDDING_BACKOFF_S", "0.5")),
        )
        config.validate()
        return config

    def validate(self) -> None:
        if not self.model:
            raise NIMEmbeddingError("NVIDIA_EMBEDDING_MODEL is required")
        if not self.base_url.startswith(("https://", "http://")):
            raise NIMEmbeddingError("NVIDIA_EMBEDDING_BASE_URL must be an HTTP(S) URL")
        if self.dimensions != REQUIRED_EMBEDDING_DIMENSIONS:
            raise NIMEmbeddingError(
                f"EMBEDDING_DIMENSIONS must be {REQUIRED_EMBEDDING_DIMENSIONS}, "
                f"got {self.dimensions}"
            )
        if self.timeout_seconds <= 0:
            raise NIMEmbeddingError("NVIDIA_EMBEDDING_TIMEOUT_S must be positive")
        if self.max_attempts < 1:
            raise NIMEmbeddingError("NVIDIA_EMBEDDING_MAX_ATTEMPTS must be at least 1")
        if self.backoff_seconds < 0:
            raise NIMEmbeddingError("NVIDIA_EMBEDDING_BACKOFF_S cannot be negative")


class NIMEmbeddingClient:
    """Typed, retrying NVIDIA NIM client that never returns unverified vectors."""

    def __init__(
        self,
        config: NIMEmbeddingConfig,
        *,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        config.validate()
        self.config = config
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=config.timeout_seconds)
        self._sleep = sleep

    @classmethod
    def from_env(cls) -> NIMEmbeddingClient:
        return cls(NIMEmbeddingConfig.from_env())

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> NIMEmbeddingClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def embed_query(self, text: str) -> list[float]:
        return self.embed([text], input_type=EmbeddingInputType.QUERY)[0]

    def embed_passages(self, texts: Sequence[str]) -> list[list[float]]:
        return self.embed(texts, input_type=EmbeddingInputType.PASSAGE)

    def embed(
        self,
        texts: Sequence[str],
        *,
        input_type: EmbeddingInputType,
    ) -> list[list[float]]:
        normalized = self._validate_input(texts)
        payload = {
            "model": self.config.model,
            "input": normalized,
            "input_type": input_type.value,
            "encoding_format": "float",
            "dimensions": self.config.dimensions,
            "truncate": "END",
        }

        last_error: Exception | None = None
        for attempt in range(1, self.config.max_attempts + 1):
            try:
                response = self._client.post(
                    f"{self.config.base_url}/embeddings",
                    headers={
                        "Authorization": f"Bearer {self.config.api_key}",
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                if response.status_code in _TRANSIENT_STATUS_CODES:
                    raise NIMEmbeddingError(
                        f"NVIDIA NIM transient HTTP {response.status_code}"
                    )
                response.raise_for_status()
                return self._parse_response(response, expected_count=len(normalized))
            except (httpx.TimeoutException, httpx.NetworkError, NIMEmbeddingError) as exc:
                last_error = exc
                if attempt == self.config.max_attempts:
                    break
                self._sleep(self.config.backoff_seconds * (2 ** (attempt - 1)))
            except httpx.HTTPStatusError as exc:
                raise NIMEmbeddingError(
                    f"NVIDIA NIM rejected the embedding request with HTTP "
                    f"{exc.response.status_code}"
                ) from exc

        raise NIMEmbeddingError(
            f"NVIDIA NIM embedding failed after {self.config.max_attempts} attempts"
        ) from last_error

    def probe(self) -> None:
        """Raise unless NIM returns one valid 384-dimensional query vector."""
        self.embed_query("knowledge service readiness probe")

    @staticmethod
    def _validate_input(texts: Sequence[str]) -> list[str]:
        if isinstance(texts, (str, bytes)) or not texts:
            raise ValueError("texts must be a non-empty sequence of strings")
        normalized: list[str] = []
        for text in texts:
            if not isinstance(text, str) or not text.strip():
                raise ValueError("every embedding input must be a non-empty string")
            normalized.append(text.strip())
        return normalized

    def _parse_response(
        self,
        response: httpx.Response,
        *,
        expected_count: int,
    ) -> list[list[float]]:
        try:
            payload: Any = response.json()
        except ValueError as exc:
            raise NIMEmbeddingError("NVIDIA NIM returned invalid JSON") from exc

        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list) or len(data) != expected_count:
            raise NIMEmbeddingError(
                f"NVIDIA NIM returned {len(data) if isinstance(data, list) else 0} "
                f"vectors; expected {expected_count}"
            )

        if all(isinstance(item, dict) and isinstance(item.get("index"), int) for item in data):
            data = sorted(data, key=lambda item: item["index"])

        vectors: list[list[float]] = []
        for item in data:
            raw_vector = item.get("embedding") if isinstance(item, dict) else None
            if not isinstance(raw_vector, list):
                raise NIMEmbeddingError("NVIDIA NIM response is missing an embedding vector")
            if len(raw_vector) != self.config.dimensions:
                raise NIMEmbeddingError(
                    f"NVIDIA NIM returned {len(raw_vector)} dimensions; "
                    f"expected {self.config.dimensions}"
                )
            try:
                vector = [float(value) for value in raw_vector]
            except (TypeError, ValueError) as exc:
                raise NIMEmbeddingError("NVIDIA NIM returned a non-numeric vector") from exc
            if not all(math.isfinite(value) for value in vector):
                raise NIMEmbeddingError("NVIDIA NIM returned non-finite vector values")
            if not any(value != 0.0 for value in vector):
                raise NIMEmbeddingError("NVIDIA NIM returned a zero vector")
            vectors.append(vector)
        return vectors
