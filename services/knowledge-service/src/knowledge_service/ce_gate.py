"""Small multilingual cross-encoder relevance GATE (RAG phase 8.1).

Solves the same-language cosine inversion: on a 100% French corpus, dense cosine inflates noise
(recruitment 0.86) above real answers (roaming-signal 0.85), so no FLOOR separates them. A
cross-encoder reads (query, passage) jointly and emits calibrated relevance, so noise lands near
0 and a threshold works. Unlike the retired 1.1 GB jina, this is ~118 MB and runs ONLY on the
<=12 survivors of the cheap dense+lexical gates, so it is realtime-safe (~80-150 ms) and RAM-light.
"""
from __future__ import annotations

import logging
import math
import os
import threading

logger = logging.getLogger(__name__)

DEFAULT_CE_MODEL = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"


class CEGateError(RuntimeError):
    """The cross-encoder gate could not score. Surfaced so the caller can degrade gracefully."""


def ce_gate_enabled() -> bool:
    return os.getenv("KNOWLEDGE_CE_GATE_ENABLED", "true").strip().lower() == "true"


def ce_model_name() -> str:
    return os.getenv("KNOWLEDGE_CE_MODEL", DEFAULT_CE_MODEL)


def ce_threshold() -> float:
    return float(os.getenv("KNOWLEDGE_CE_THRESHOLD", "0.30"))


def ce_max_candidates() -> int:
    return max(1, int(os.getenv("KNOWLEDGE_CE_MAX_CANDIDATES", "12")))


class SmallCrossEncoderGate:
    """Tiny, lazy, process-wide cross-encoder gate (~118 MB, torch-CPU).

    Mirrors the reranker.py structure but is a *gate* (keeps passages >= threshold) and points
    at the small mMARCO mMiniLMv2 model instead of the retired 1.1 GB jina. Cache location is
    controlled by the HF_HOME env var (set in the Dockerfile), not a constructor argument —
    sentence-transformers 3.3.1 CrossEncoder does not accept cache_folder.
    """

    def __init__(self, model_name: str | None = None) -> None:
        self._model_name = model_name or ce_model_name()
        self._model = None
        self._lock = threading.Lock()

    def _ensure_model(self):
        if self._model is not None:
            return self._model
        with self._lock:
            if self._model is None:
                try:
                    from sentence_transformers import CrossEncoder
                except Exception as exc:
                    raise CEGateError(f"sentence-transformers import failed: {exc}") from exc
                try:
                    import torch
                    torch.set_num_threads(int(os.getenv("KNOWLEDGE_CE_THREADS", "4")))
                except Exception:
                    pass
                try:
                    # torch-CPU path. Cache location comes from HF_HOME (set in the Dockerfile).
                    # No cache_folder / backend / model_kwargs — unsupported in
                    # sentence-transformers 3.3.1.
                    self._model = CrossEncoder(
                        self._model_name,
                        max_length=int(os.getenv("KNOWLEDGE_CE_MAX_LENGTH", "256")),
                        device="cpu",
                    )
                except Exception as exc:
                    raise CEGateError(f"cannot load CE model {self._model_name!r}: {exc}") from exc
                logger.info("CE gate loaded: %s", self._model_name)
        return self._model

    def scores(self, query: str, passages: list[str]) -> list[float]:
        """Score (query, passage) pairs jointly; return sigmoid-normalized 0-1 relevance."""
        if not passages:
            return []
        model = self._ensure_model()
        try:
            raw = model.predict([(query, p) for p in passages], apply_softmax=False)
        except Exception as exc:
            raise CEGateError(f"CE scoring failed: {exc}") from exc
        return [1.0 / (1.0 + math.exp(-float(v))) for v in raw]   # logit -> 0-1

    def health_check(self) -> None:
        """Prove the model loads and emits a score. Raises CEGateError on any problem."""
        if len(self.scores("bonjour", ["bonjour le monde"])) != 1:
            raise CEGateError("CE gate health check returned no score")


_ce: SmallCrossEncoderGate | None = None
_ce_lock = threading.Lock()


def get_ce_gate() -> SmallCrossEncoderGate:
    """Process-wide CE gate, built lazily so a cold start does not block the container."""
    global _ce
    if _ce is None:
        with _ce_lock:
            if _ce is None:
                _ce = SmallCrossEncoderGate()
    return _ce
