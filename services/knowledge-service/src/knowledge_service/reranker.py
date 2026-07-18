"""Cross-encoder reranking (RAG phase 7).

Why this exists, in one measurement. On the real 16-document corpus:

    control query "how do I fix my washing machine"  -> 0.8411 (faq/wifi-problems.pdf)
    Arabic true positive "كيف أفعل التجوال الدولي"     -> 0.8310 (roaming-activation)

A question with nothing to do with telecom scores HIGHER than a correct Arabic answer. The two
distributions are not merely tight, they are inverted: no FLOOR can drop the noise without
dropping every Arabic answer with it. Thresholds on bi-encoder cosine are finished here, and no
amount of tuning brings them back.

The cause is structural. A bi-encoder embeds the query and the passage independently, so it can
only compare two summaries; "how do I fix my ..." lands next to troubleshooting prose because
the *shape* matches, and cross-language pairs score systematically lower than same-language ones
regardless of meaning. A cross-encoder reads the query and the passage TOGETHER with full
attention, so it can see that "washing machine" is not "wifi router" - and it compares meaning
rather than embedding geometry, which is why its scores do not inherit the language penalty.

Cost, honestly: jina-reranker-v2-base-multilingual is ~1.11 GB and runs per candidate, so it is
the most expensive component in this pipeline. It earns that only because the cheap option is
now measurably broken. It is the only multilingual reranker fastembed ships - the 0.08 GB
ms-marco models are English-only and cannot score a French or Arabic question at all.
"""
from __future__ import annotations

import logging
import math
import os
import threading

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "jinaai/jina-reranker-v2-base-multilingual"
DEFAULT_CACHE_DIR = "/opt/models"


class RerankError(RuntimeError):
    """Reranking failed. Surfaced so retrieval can decide, never silently skipped."""


def reranker_enabled() -> bool:
    """Off by default in Phase 8: the hybrid dense+BM25+RRF is the realtime relevance gate.
    Enable for offline A/B evaluation — 1.1 GB RAM, 2-5s per query."""
    return os.getenv("KNOWLEDGE_RERANKER_ENABLED", "false").strip().lower() == "true"


def reranker_model_name() -> str:
    return os.getenv("KNOWLEDGE_RERANKER_MODEL", DEFAULT_MODEL)


def rerank_candidates() -> int:
    """How many dense hits to rerank.

    The reranker can only choose from what the bi-encoder retrieved, so this is the recall
    ceiling - but every candidate is a full forward pass, so it is also the latency bill on a
    caller's line. 12 keeps both honest.
    """
    return max(1, int(os.getenv("KNOWLEDGE_RERANK_CANDIDATES", "12")))


def rerank_threshold() -> float:
    """Minimum relevance probability (0-1) for a passage to reach the agent.

    This replaces FLOOR/RELATIVE, which operated on cosine. Cross-encoder scores are calibrated
    relevance, not geometric similarity: an irrelevant passage lands near 0 instead of 0.84.
    """
    return float(os.getenv("KNOWLEDGE_RERANK_THRESHOLD", "0.5"))


def sigmoid(value: float) -> float:
    """Logit -> probability. The model emits logits; a 0-1 scale is what stays interpretable
    across models and is what the threshold is expressed in."""
    if value >= 0:
        return 1.0 / (1.0 + math.exp(-value))
    exponent = math.exp(value)  # avoid overflow for very negative logits
    return exponent / (1.0 + exponent)


class LocalReranker:
    """Scores (query, passage) pairs jointly. Loads the ONNX session once per process."""

    def __init__(self, model_name: str | None = None, cache_dir: str | None = None) -> None:
        self._model_name = model_name or reranker_model_name()
        self._cache_dir = cache_dir or os.getenv("EMBEDDING_CACHE_DIR", DEFAULT_CACHE_DIR)
        self._threads = int(os.getenv("KNOWLEDGE_RERANKER_THREADS", "0")) or None
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
                    from fastembed.rerank.cross_encoder import TextCrossEncoder
                except ImportError as exc:
                    raise RerankError(f"fastembed cross-encoder unavailable: {exc}") from exc
                try:
                    kwargs = {"model_name": self._model_name, "cache_dir": self._cache_dir}
                    if self._threads:
                        kwargs["threads"] = self._threads
                    self._model = TextCrossEncoder(**kwargs)
                except Exception as exc:
                    raise RerankError(
                        f"cannot load reranker {self._model_name!r} from {self._cache_dir!r}: {exc}"
                    ) from exc
                logger.info("reranker loaded: %s", self._model_name)
        return self._model

    def score(self, query: str, documents: list[str]) -> list[float]:
        """Relevance probability (0-1) per document, in the order given."""
        if not documents:
            return []
        model = self._ensure_model()
        try:
            raw = list(model.rerank(query, documents))
        except Exception as exc:
            raise RerankError(f"reranking failed for {len(documents)} passage(s): {exc}") from exc
        if len(raw) != len(documents):
            raise RerankError(f"reranker returned {len(raw)} scores for {len(documents)} inputs")
        return [sigmoid(float(value)) for value in raw]

    def health_check(self) -> None:
        """Prove the model loads and scores. Raises on any problem."""
        scores = self.score("health check", ["a health check passage"])
        if len(scores) != 1:
            raise RerankError("reranker health check returned no score")


_reranker: LocalReranker | None = None
_reranker_lock = threading.Lock()


def get_reranker() -> LocalReranker:
    """Process-wide reranker (the ONNX session is ~1.1 GB; load it once)."""
    global _reranker
    if _reranker is None:
        with _reranker_lock:
            if _reranker is None:
                _reranker = LocalReranker()
    return _reranker
