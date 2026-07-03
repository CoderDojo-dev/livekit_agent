# syntax=docker/dockerfile:1
# Build from the REPO ROOT:  docker build -f apps/agent-worker/Dockerfile -t agent-worker .
FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
RUN useradd -m app
COPY packages/ ./packages/
RUN pip install ./packages/domain-core ./packages/persistence ./packages/audit-trail ./packages/pii-shield ./packages/observability-kit ./packages/service-auth ./packages/cache ./packages/object-storage ./packages/notification-client ./packages/integration-adapters
COPY apps/agent-worker/ ./apps/agent-worker/
RUN pip install ./apps/agent-worker
USER app
CMD ["python", "apps/agent-worker/src/server.py", "start"]
