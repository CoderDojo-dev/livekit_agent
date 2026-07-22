# syntax=docker/dockerfile:1
# Build from the REPO ROOT:  docker build -f services/ocs-billing-sim/Dockerfile -t ocs-billing-sim .
FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
RUN useradd -m app
COPY packages/ ./packages/
RUN pip install ./packages/domain-core ./packages/persistence ./packages/service-auth
COPY services/ocs-billing-sim/ ./services/ocs-billing-sim/
RUN pip install ./services/ocs-billing-sim
USER app
EXPOSE 8107
HEALTHCHECK --interval=15s --timeout=5s --retries=5 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8107/health')" || exit 1
CMD ["uvicorn", "ocs_billing_sim.main:app", "--host", "0.0.0.0", "--port", "8107"]
