FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gosu \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY alembic.ini ./
COPY alembic ./alembic
COPY src ./src
COPY docker/entrypoint.sh /app/docker/entrypoint.sh

RUN pip install --upgrade pip && pip install ".[ui]" \
    && apt-get purge -y build-essential && apt-get autoremove -y \
    && chmod +x /app/docker/entrypoint.sh \
    && useradd -m -u 1001 forensics \
    && mkdir -p /data/uploads /data/traces \
    && chown -R forensics:forensics /data

EXPOSE 8090

HEALTHCHECK --interval=10s --timeout=3s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8090/health').read()"

ENTRYPOINT ["/app/docker/entrypoint.sh"]
