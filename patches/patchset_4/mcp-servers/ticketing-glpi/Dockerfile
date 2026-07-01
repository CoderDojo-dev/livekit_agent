# syntax=docker/dockerfile:1
# Build from the REPO ROOT:  docker build -f mcp-servers/ticketing-glpi/Dockerfile -t ticketing-glpi .
FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
RUN useradd -m app
COPY packages/ ./packages/
RUN pip install ./packages/domain-core ./packages/persistence ./packages/audit-trail ./packages/pii-shield ./packages/observability-kit ./packages/service-auth ./packages/cache ./packages/object-storage ./packages/notification-client ./packages/integration-adapters
COPY mcp-servers/ticketing-glpi/ ./mcp-servers/ticketing-glpi/
RUN pip install ./mcp-servers/ticketing-glpi
USER app
EXPOSE 8202
CMD ["python", "-m", "ticketing_glpi.server"]
