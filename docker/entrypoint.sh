#!/bin/bash
set -euo pipefail

echo "==> Starte DjangoTestProject Entrypoint"

# Warte auf PostgreSQL
if [ -n "${DATABASE_URL:-}" ]; then
    echo "==> Warte auf PostgreSQL..."
    until python -c "
import os, sys, psycopg2, urllib.parse as p
url = os.environ['DATABASE_URL']
r = p.urlparse(url)
try:
    psycopg2.connect(
        host=r.hostname, port=r.port or 5432,
        dbname=r.path.lstrip('/'), user=r.username, password=r.password,
        connect_timeout=3
    ).close()
    sys.exit(0)
except Exception:
    sys.exit(1)
" 2>/dev/null; do
        echo "   PostgreSQL nicht erreichbar – warte 2s..."
        sleep 2
    done
    echo "==> PostgreSQL erreichbar"
fi

# Datenbankmigrationen
echo "==> Führe Migrationen aus..."
python manage.py migrate --noinput

# Superuser aus Umgebungsvariablen anlegen (optional)
if [ "${DJANGO_SUPERUSER_EMAIL:-}" ] && [ "${DJANGO_SUPERUSER_PASSWORD:-}" ]; then
    echo "==> Lege Superuser an (falls noch nicht vorhanden)..."
    python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
email = '${DJANGO_SUPERUSER_EMAIL}'
if not User.objects.filter(email=email).exists():
    User.objects.create_superuser(
        username=email.split('@')[0],
        email=email,
        password='${DJANGO_SUPERUSER_PASSWORD}'
    )
    print('Superuser angelegt')
else:
    print('Superuser existiert bereits')
" 2>/dev/null || true
fi

# Starte Anwendung
if [ "${1:-}" = "gunicorn" ]; then
    echo "==> Starte Gunicorn auf Port ${PORT:-8000}..."
    exec gunicorn config.wsgi:application \
        --bind "0.0.0.0:${PORT:-8000}" \
        --workers "${GUNICORN_WORKERS:-4}" \
        --worker-class "${GUNICORN_WORKER_CLASS:-sync}" \
        --worker-tmp-dir /dev/shm \
        --timeout "${GUNICORN_TIMEOUT:-30}" \
        --graceful-timeout "${GUNICORN_GRACEFUL_TIMEOUT:-20}" \
        --keep-alive "${GUNICORN_KEEP_ALIVE:-5}" \
        --max-requests "${GUNICORN_MAX_REQUESTS:-1000}" \
        --max-requests-jitter "${GUNICORN_MAX_REQUESTS_JITTER:-100}" \
        --log-level "${GUNICORN_LOG_LEVEL:-info}" \
        --access-logfile - \
        --error-logfile -
else
    exec "$@"
fi
