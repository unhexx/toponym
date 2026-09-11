FROM python:3.12-slim-bookworm

LABEL org.opencontainers.image.source="https://github.com/unhexx/toponym" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.title="toponym"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TOPONYM_BIND=0.0.0.0 \
    TOPONYM_PORT=8099 \
    TOPONYM_DB=/app/knowledge/registry.db \
    TOPONYM_ALLOW_NON_LOOPBACK=1

WORKDIR /app

COPY pyproject.toml README.md LICENSE datapackage.json ./
COPY scripts ./scripts
COPY schema ./schema
COPY data ./data
COPY ontology ./ontology

RUN pip install --no-cache-dir . \
    && groupadd --gid 10001 toponym \
    && useradd --system --uid 10001 --gid 10001 --home /app --no-create-home toponym \
    && mkdir -p /app/knowledge \
    && chown -R 10001:10001 /app/knowledge \
    && chmod +x /app/scripts/entrypoint.sh

USER 10001:10001

EXPOSE 8099

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
