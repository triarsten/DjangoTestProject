# =============================================================================
# Stage 1: Builder
# =============================================================================
FROM python:3.12-slim AS builder

# System-Abhängigkeiten für psycopg2 und Build-Tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Requirements separat kopieren für besseres Layer-Caching
COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt

# =============================================================================
# Stage 2: Runtime
# =============================================================================
FROM python:3.12-slim AS runtime

# Nur Runtime-Abhängigkeiten
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Non-root User für Sicherheit
RUN groupadd --gid 1000 django && \
    useradd --uid 1000 --gid django --shell /bin/bash --create-home django

# Python-Packages aus Builder-Stage
COPY --from=builder /install /usr/local

WORKDIR /app

# Anwendungscode kopieren
COPY --chown=django:django . .

# Entrypoint-Script
COPY --chown=django:django docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Static Files einsammeln (ohne DB-Verbindung)
ENV DJANGO_SETTINGS_MODULE=config.settings \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PORT=8000

USER django

# Static Files vorab einsammeln (SECRET_KEY nur für diesen Step)
RUN SECRET_KEY=dummy-build-secret \
    DATABASE_URL=postgres://dummy:dummy@localhost/dummy \
    python manage.py collectstatic --noinput --clear 2>/dev/null || true

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health/ || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn"]
