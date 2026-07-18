# syntax=docker/dockerfile:1
# Build from the REPO ROOT:  docker build -f services/knowledge-service/Dockerfile -t knowledge-service .
FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
# Weights are baked in at build time: the container never downloads a model at runtime, so cold
# start is deterministic and the service works without internet access.
ENV EMBEDDING_MODEL=intfloat/multilingual-e5-small \
    EMBEDDING_DIMENSIONS=384 \
    EMBEDDING_CACHE_DIR=/opt/models
WORKDIR /app
RUN useradd -m app
COPY packages/ ./packages/
RUN pip install ./packages/domain-core ./packages/persistence ./packages/audit-trail ./packages/pii-shield ./packages/observability-kit ./packages/service-auth ./packages/cache ./packages/object-storage ./packages/notification-client ./packages/integration-adapters
COPY services/knowledge-service/ ./services/knowledge-service/
COPY scripts/ /app/scripts/
RUN pip install ./services/knowledge-service
# Pre-download + verify the ONNX weights into the image. Uses the service's own code path so the
# build is always testing the exact code that runs in production.
RUN mkdir -p /opt/models \
 && python -c "from knowledge_service.embeddings import get_embedder; e=get_embedder(); e.health_check(); print('model baked, dims', e.dimensions)" \
 && python -c "from knowledge_service.embeddings import get_sparse_embedder, hybrid_enabled; s=get_sparse_embedder() if hybrid_enabled() else None; s.health_check() if s else None; print('sparse baked:', s.model_name if s else 'disabled')" \
 && chown -R app:app /opt/models
USER app
EXPOSE 8102
# start-period covers the ONNX warm-up of the embedder (~30s). The sparse BM25 model is tiny
# (~instant). The 1.1 GB cross-encoder reranker is NOT baked (disabled by default in Phase 8).
HEALTHCHECK --interval=15s --timeout=10s --retries=5 --start-period=60s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8102/health')" || exit 1
CMD ["uvicorn", "knowledge_service.main:app", "--host", "0.0.0.0", "--port", "8102"]
