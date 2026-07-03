# syntax=docker/dockerfile:1
# Build from the REPO ROOT:  docker build -f mcp-servers/ai-knowledge-rag/Dockerfile -t ai-knowledge-rag .
FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
RUN useradd -m app
COPY packages/ ./packages/
RUN pip install ./packages/domain-core ./packages/persistence ./packages/audit-trail ./packages/pii-shield ./packages/observability-kit ./packages/service-auth ./packages/cache ./packages/object-storage ./packages/notification-client ./packages/integration-adapters
COPY mcp-servers/ai-knowledge-rag/ ./mcp-servers/ai-knowledge-rag/
RUN pip install ./mcp-servers/ai-knowledge-rag
USER app
EXPOSE 8201
HEALTHCHECK --interval=15s --timeout=5s --retries=5 CMD python -c "import socket; s=socket.create_connection(('127.0.0.1', 8201), 3); s.close()" || exit 1
CMD ["python", "-m", "ai_knowledge_rag.server"]
