# syntax=docker/dockerfile:1
# Build from the REPO ROOT:  docker build -f services/execution-service/Dockerfile -t execution-service .
FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
RUN useradd -m app
COPY packages/ ./packages/
RUN pip install ./packages/domain-core ./packages/persistence ./packages/audit-trail ./packages/pii-shield ./packages/observability-kit ./packages/service-auth ./packages/cache ./packages/object-storage ./packages/notification-client ./packages/integration-adapters
COPY services/execution-service/ ./services/execution-service/
RUN pip install ./services/execution-service
USER app
EXPOSE 8105
HEALTHCHECK --interval=15s --timeout=5s --retries=5 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8105/health')" || exit 1
CMD ["uvicorn", "execution_service.main:app", "--host", "0.0.0.0", "--port", "8105"]
