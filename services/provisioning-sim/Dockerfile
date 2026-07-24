# syntax=docker/dockerfile:1
# Build from the REPO ROOT:  docker build -f services/provisioning-sim/Dockerfile -t provisioning-sim .
FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
RUN useradd -m app
# The ledger writes the real domain tables, so the shared packages must be installed - without
# them `persistence` and `service_auth` are missing and the service fails to import at startup.
COPY packages/ ./packages/
RUN pip install ./packages/domain-core ./packages/persistence ./packages/service-auth
COPY services/provisioning-sim/ ./services/provisioning-sim/
RUN pip install ./services/provisioning-sim
USER app
EXPOSE 8109
HEALTHCHECK --interval=15s --timeout=5s --retries=5 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8109/health')" || exit 1
CMD ["uvicorn", "provisioning_sim.main:app", "--host", "0.0.0.0", "--port", "8109"]
