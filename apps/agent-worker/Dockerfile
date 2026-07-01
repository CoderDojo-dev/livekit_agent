FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e . || true
COPY src ./src
CMD ["python", "-m", "entrypoints.worker"]