# syntax=docker/dockerfile:1
# Build from the REPO ROOT:  docker build -f services/nms-sim/Dockerfile -t nms-sim .
FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
RUN useradd -m app
COPY packages/ ./packages/
RUN pip install ./packages/domain-core ./packages/persistence ./packages/service-auth
COPY services/nms-sim/ ./services/nms-sim/
RUN pip install ./services/nms-sim
USER app
EXPOSE 8108
HEALTHCHECK --interval=15s --timeout=5s --retries=5 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8108/health')" || exit 1
CMD ["uvicorn", "nms_sim.main:app", "--host", "0.0.0.0", "--port", "8108"]
