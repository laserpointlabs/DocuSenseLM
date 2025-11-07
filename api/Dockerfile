# syntax=docker/dockerfile:1.4
FROM python:3.11-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on

WORKDIR /app

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    tesseract-ocr \
    poppler-utils \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements.txt

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip setuptools wheel && \
    pip install --progress-bar on -r requirements.txt --index-url https://pypi.org/simple/ --extra-index-url https://download.pytorch.org/whl/cu121

COPY api/ ./api/
COPY ingest/ ./ingest/
COPY llm/ ./llm/
COPY ontology/ ./ontology/
COPY scripts/ ./scripts/

ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-exclude", "scripts/*", "--reload-exclude", "*.pyc"]
