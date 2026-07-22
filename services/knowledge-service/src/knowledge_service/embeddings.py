"""Strict embedding client for the knowledge pipeline (RAG phase 2).

Uses `intfloat/multilingual-e5-small` — an asymmetric ONNX model tuned for
open-domain QA / passage retrieval. Unlike symmetric models (paraphrase
MinilM), E5 requires a prefix on every text to tell the encoder which role it
plays in the asymmetric pair:

  query: "what is my balance?"    (caller question at search time)
  passage: "your balance is..."   (corpus chunk during ingestion)

Both prefixes are prepended inside `embed()` so callers never need to think
about them.

Why not a hosted API? See earlier docs — every caller question would add a
network round-trip and a new failure mode to the real-time voice path, and
NVIDIA's trial credits are exhausted after a single full ingestion.

`intfloat/multilingual-e5-small` is a 118M-parameter distilled model that
emits **384**-dimensional vectors — exactly what `knowledge.chunks` and the
Qdrant collection are built for — covers `ar`/`fr`/`en` among 100 languages,
and maps every language into one aligned vector space, so a French question
retrieves an English procedure without translating anything. It runs quantized
on CPU: no GPU, no API key, no quota, no rate limit.

The client is deliberately strict. It validates the dimension of every vector it
produces and raises instead of returning something the vector store would
silently accept as garbage.
"""
from __future__ import annotations

import functools
import logging
import os
import threading
from contextlib import suppress
from enum import StrEnum

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "intfloat/multilingual-e5-small"
DEFAULT_DIMENSIONS = 384
DEFAULT_CACHE_DIR = "/opt/models"

# --- Sparse BM25 embedder (RAG phase 8: hybrid dense + sparse retrieval) -----------------
DEFAULT_SPARSE_MODEL = "Qdrant/bm25"


def sparse_model_name() -> str:
    return os.getenv("KNOWLEDGE_SPARSE_MODEL", DEFAULT_SPARSE_MODEL)


def hybrid_enabled() -> bool:
    return os.getenv("KNOWLEDGE_HYBRID_ENABLED", "true").strip().lower() == "true"

# fastembed does not natively know about E5; it must be registered so the
# pipeline can pick the right pooling strategy.
_CUSTOM_MODELS: dict[str, dict] = {
    "intfloat/multilingual-e5-small": {
        "pooling": "mean",   # E5 uses mean pooling (not CLS)
        "normalize": True,   # cosine-similarity-ready
    },
}

_PREFIX_MODELS: frozenset = frozenset({
    "intfloat/multilingual-e5-small",
    "intfloat/multilingual-e5-base",
    "intfloat/multilingual-e5-large",
    "intfloat/e5-small-v2",
    "intfloat/e5-base-v2",
    "intfloat/e5-large-v2",
})


class InputType(StrEnum):
    """Asymmetric retrieval roles (callers must pick one — the model prepends
    the correct prefix, so a future model swap won't silently break retrieval)."""

    PASSAGE = "passage"
    QUERY = "query"


class EmbeddingError(RuntimeError):
    """An embedding could not be produced correctly. Never swallow this into a fake vector."""


def embedding_model_name() -> str:
    """The configured embedding model (must match what the collection was built with)."""
    return os.getenv("EMBEDDING_MODEL", DEFAULT_MODEL)


def embedding_dimensions() -> int:
    """The configured vector width; validated against the model's real output on every call."""
    raw = os.getenv("EMBEDDING_DIMENSIONS", str(DEFAULT_DIMENSIONS))
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise EmbeddingError(f"EMBEDDING_DIMENSIONS is not an integer: {raw!r}") from exc
    if value <= 0:
        raise EmbeddingError(f"EMBEDDING_DIMENSIONS must be positive, got {value}")
    return value


def embedding_cache_dir() -> str:
    """Where the ONNX weights live. Baked into the image at build time (no runtime download)."""
    return os.getenv("EMBEDDING_CACHE_DIR", DEFAULT_CACHE_DIR)


def uses_e5_prefix(model_name: str) -> bool:
    """True if *model_name* needs the ``query: `` / ``passage: `` prefix.

    Only models from the E5 / instructor family require this. Symmetric models
    like paraphrase-MiniLM share one space and should NOT be prefixed.
    """
    return model_name in _PREFIX_MODELS


def ensure_model_registered() -> None:
    """Register custom model configs with fastembed so the right pooling
    strategy is picked. Idempotent.
    """
    try:
        from fastembed import TextEmbedding
        from fastembed.common.model_description import ModelSource, PoolingType
    except ImportError:
        return  # will be caught later by _ensure_model
    for model_name, _config in _CUSTOM_MODELS.items():
        with suppress(ValueError):
            TextEmbedding.add_custom_model(
                model=model_name,
                pooling=PoolingType.MEAN,
                normalization=True,
                sources=ModelSource(hf=model_name),
                dim=DEFAULT_DIMENSIONS,
            )


class LocalEmbedder:
    """Loads the ONNX model once per process and embeds text to fixed-width float vectors.

    Thread-safe lazy load. Supports asymmetric retrieval via E5 prefixes.
    """

    def __init__(
        self,
        model_name: str | None = None,
        dimensions: int | None = None,
        cache_dir: str | None = None,
    ) -> None:
        self._model_name = model_name or embedding_model_name()
        self._dimensions = dimensions if dimensions is not None else embedding_dimensions()
        self._cache_dir = cache_dir or embedding_cache_dir()
        self._model = None
        self._lock = threading.Lock()
        # Pre-compute the prefix requirement once (the model is fixed for the
        # lifetime of the process).
        self._prefixed = uses_e5_prefix(self._model_name)
        # LRU cache on query embeddings: repeated FAQ questions are common on a voice line,
        # and the embedding is deterministic per text so caching is safe. Vectors are converted
        # to tuples (hashable/immutable) for the cache and back to lists on read.
        self._query_cache = functools.lru_cache(
            maxsize=int(os.getenv("KNOWLEDGE_QUERY_CACHE", "256"))
        )(self._embed_query_uncached)

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def _ensure_model(self):
        if self._model is not None:
            return self._model
        with self._lock:
            if self._model is None:
                ensure_model_registered()
                try:
                    from fastembed import TextEmbedding
                except ImportError as exc:
                    raise EmbeddingError(f"fastembed is not installed: {exc}") from exc
                try:
                    self._model = TextEmbedding(
                        model_name=self._model_name,
                        cache_dir=self._cache_dir,
                    )
                except Exception as exc:
                    raise EmbeddingError(
                        f"cannot load embedding model {self._model_name!r} "
                        f"from {self._cache_dir!r}: {exc}"
                    ) from exc
                logger.info(
                    "embedding model loaded: %s (%d dimensions, prefixes=%s)",
                    self._model_name, self._dimensions, self._prefixed,
                )
        return self._model

    def _validate(self, vector: list[float]) -> list[float]:
        if len(vector) != self._dimensions:
            raise EmbeddingError(
                f"model {self._model_name!r} returned {len(vector)} dimensions, "
                f"expected {self._dimensions}; the Qdrant collection would reject or "
                f"silently corrupt this vector"
            )
        return vector

    def embed(self, texts: list[str], input_type: InputType) -> list[list[float]]:
        """Embed ``texts`` in one batch. Prepends ``query: `` / ``passage: `` prefix
        when the model is an asymmetric one that needs it.

        Raises EmbeddingError rather than returning garbage.
        """
        if not isinstance(texts, list):
            raise EmbeddingError(f"texts must be a list, got {type(texts).__name__}")
        if not texts:
            return []
        cleaned: list[str] = []
        for index, text in enumerate(texts):
            if not isinstance(text, str) or not text.strip():
                raise EmbeddingError(f"texts[{index}] is empty or not a string")
            cleaned.append(text.strip())

        # E5 requires a prefix that tells the encoder which role this text
        # plays in the asymmetric pair. For symmetric models the prefix is
        # empty and the text is passed through unchanged.
        prefix = f"{input_type.value}: " if self._prefixed else ""
        if prefix:
            cleaned = [f"{prefix}{text}" for text in cleaned]

        model = self._ensure_model()
        try:
            raw = list(model.embed(cleaned))
        except Exception as exc:
            raise EmbeddingError(
                f"embedding failed for {len(cleaned)} {input_type.value} text(s): {exc}"
            ) from exc

        if len(raw) != len(cleaned):
            raise EmbeddingError(
                f"model returned {len(raw)} vectors for {len(cleaned)} inputs"
            )
        return [self._validate([float(value) for value in vector]) for vector in raw]

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        """Embed corpus chunks for indexing (prepends ``passage: `` for E5)."""
        return self.embed(texts, InputType.PASSAGE)

    def _embed_query_uncached(self, text: str) -> tuple[float, ...]:
        return tuple(self.embed([text], InputType.QUERY)[0])

    def embed_query(self, text: str) -> list[float]:
        """Embed a single caller question for search (prepends ``query: `` for E5).

        Cached: identical question text returns the same vector without re-running the model.
        """
        return list(self._query_cache(text.strip()))

    def health_check(self) -> None:
        """Prove the model loads and emits the configured width. Raises on any problem."""
        vector = self.embed(["health check"], InputType.QUERY)[0]
        self._validate(vector)


_embedder: LocalEmbedder | None = None
_embedder_lock = threading.Lock()


def get_embedder() -> LocalEmbedder:
    """Process-wide embedder (the ONNX session is expensive; load it once)."""
    global _embedder
    if _embedder is None:
        with _embedder_lock:
            if _embedder is None:
                _embedder = LocalEmbedder()
    return _embedder


class LocalSparseEmbedder:
    """BM25 sparse vectors via fastembed. CPU-only, no weights to download of note (~tiny).

    Produces (indices, values) sparse vectors. Stored server-side in Qdrant with an IDF
    modifier so document-frequency weighting is computed across the whole collection.
    """

    def __init__(self, model_name: str | None = None, cache_dir: str | None = None) -> None:
        self._model_name = model_name or sparse_model_name()
        self._cache_dir = cache_dir or embedding_cache_dir()
        self._model = None
        self._lock = threading.Lock()

    @property
    def model_name(self) -> str:
        return self._model_name

    def _ensure_model(self):
        if self._model is not None:
            return self._model
        with self._lock:
            if self._model is None:
                try:
                    from fastembed import SparseTextEmbedding
                except ImportError as exc:
                    raise EmbeddingError(f"fastembed sparse unavailable: {exc}") from exc
                try:
                    self._model = SparseTextEmbedding(
                        model_name=self._model_name, cache_dir=self._cache_dir
                    )
                except Exception as exc:
                    raise EmbeddingError(
                        f"cannot load sparse model {self._model_name!r}: {exc}"
                    ) from exc
                logger.info("sparse model loaded: %s", self._model_name)
        return self._model

    def _embed(self, texts: list[str], *, is_query: bool):
        model = self._ensure_model()
        fn = model.query_embed if is_query else model.embed
        try:
            return list(fn(texts))
        except Exception as exc:
            raise EmbeddingError(f"sparse embedding failed: {exc}") from exc

    def embed_passages(self, texts: list[str]):
        """Returns list of fastembed SparseEmbedding (has .indices, .values)."""
        return self._embed(texts, is_query=False)

    def embed_query(self, text: str):
        return self._embed([text], is_query=True)[0]

    def health_check(self) -> None:
        result = self.embed_query("health check")
        if len(result.indices) == 0:
            # empty is valid for out-of-vocab; just prove the model runs
            pass


_sparse_embedder: LocalSparseEmbedder | None = None
_sparse_lock = threading.Lock()


def get_sparse_embedder() -> LocalSparseEmbedder:
    global _sparse_embedder
    if _sparse_embedder is None:
        with _sparse_lock:
            if _sparse_embedder is None:
                _sparse_embedder = LocalSparseEmbedder()
    return _sparse_embedder
