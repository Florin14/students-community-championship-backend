# syntax=docker/dockerfile:1.7

# ---------------------------------------------------------------------------
# Builder: resolve dependencies into a self-contained virtualenv.
# Kept separate so the runtime image carries no compiler and no build cache.
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Only the requirements file, so this layer is reused on every code-only change.
COPY requirements.txt ./
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install -r requirements.txt

# ---------------------------------------------------------------------------
# Runtime
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

# Build identity, passed in by scripts/build-image.sh and surfaced at /version.
ARG VERSION=dev
ARG GIT_SHA=dev
ARG BUILD_DATE=""

LABEL org.opencontainers.image.title="students-community-championship-backend" \
      org.opencontainers.image.description="SCC championship API" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.licenses="UNLICENSED"

ENV APP_VERSION=${VERSION} \
    GIT_SHA=${GIT_SHA} \
    BUILD_DATE=${BUILD_DATE} \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # The schema is moved by Alembic in every deployed environment; create_all
    # is a local-checkout convenience only.
    AUTO_CREATE_TABLES=false \
    PORT=8000

# curl is here for the HEALTHCHECK below and nothing else.
RUN apt-get update \
    && apt-get install --no-install-recommends -y curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY --chown=appuser:appuser alembic.ini ./
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

USER appuser
EXPOSE 8000

# The app never restarts itself on a database hiccup, so the probe stays off the
# database and only asks whether the process is serving.
HEALTHCHECK --interval=15s --timeout=4s --start-period=20s --retries=4 \
    CMD curl -fsS "http://127.0.0.1:${PORT}/health" || exit 1

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["serve"]
