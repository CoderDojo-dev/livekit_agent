# syntax=docker/dockerfile:1
# Build from the REPO ROOT:  docker build -f services/knowledge-service/Dockerfile -t knowledge-service .
FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
# Weights are baked in at build time: the container never downloads a model at runtime, so cold
# start is deterministic and the service works without internet access.
ENV EMBEDDING_MODEL=intfloat/multilingual-e5-small \
    EMBEDDING_DIMENSIONS=384 \
    EMBEDDING_CACHE_DIR=/opt/models \
    HF_HOME=/opt/models
WORKDIR /app
RUN useradd -m app
COPY packages/ ./packages/
RUN pip install ./packages/domain-core ./packages/persistence ./packages/audit-trail ./packages/pii-shield ./packages/observability-kit ./packages/service-auth ./packages/cache ./packages/object-storage ./packages/notification-client ./packages/integration-adapters
# Install torch CPU-only BEFORE sentence-transformers so pip resolves the dep to the
# light (~118 MB) CPU wheel instead of pulling ~2 GB of CUDA libs.
RUN pip install --no-cache-dir torch==2.2.2 --index-url https://download.pytorch.org/whl/cpu
COPY services/knowledge-service/ ./services/knowledge-service/
COPY scripts/ /app/scripts/
RUN pip install ./services/knowledge-service
# Force numpy<2: torch 2.2.2 CPU was compiled against numpy 1.x ABI; numpy 2.x breaks it.
RUN pip install --no-cache-dir "numpy>=1.26,<2" --no-deps
# Pre-download + verify the dense and sparse weights into the image. These always succeed.
# The CE gate model is NOT pre-baked here (HuggingFace Hub is unreliable during Docker builds).
# It lazy-loads at runtime via lifespan health_check; failure degrades gracefully (no 503).
RUN mkdir -p /opt/models \
 && python -c "from knowledge_service.embeddings import get_embedder; e=get_embedder(); e.health_check(); print('model baked, dims', e.dimensions)" \
 && python -c "from knowledge_service.embeddings import get_sparse_embedder, hybrid_enabled; s=get_sparse_embedder() if hybrid_enabled() else None; s.health_check() if s else None; print('sparse baked:', s.model_name if s else 'disabled')" \
 && chown -R app:app /opt/models
USER app
EXPOSE 8102
# start-period covers the ONNX warm-up of the embedder (~30s). The sparse BM25 model is tiny
# (~instant). The CE gate model (~118 MB, torch-CPU) loads at runtime (lazy, outside readiness).
HEALTHCHECK --interval=15s --timeout=10s --retries=5 --start-period=30s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8102/health')" || exit 1
CMD ["uvicorn", "knowledge_service.main:app", "--host", "0.0.0.0", "--port", "8102"]
