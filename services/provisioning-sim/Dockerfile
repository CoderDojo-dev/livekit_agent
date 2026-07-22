# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
RUN useradd -m app
COPY services/provisioning-sim/ ./services/provisioning-sim/
RUN pip install ./services/provisioning-sim
USER app
EXPOSE 8109
HEALTHCHECK --interval=15s --timeout=5s --retries=5 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8109/health')" || exit 1
CMD ["uvicorn", "provisioning_sim.main:app", "--host", "0.0.0.0", "--port", "8109"]
