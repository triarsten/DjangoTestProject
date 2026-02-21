import time

from django.db import connection
from django.http import JsonResponse


def health(request):
    """
    Liveness + Readiness Check.
    Gibt 200 zurück wenn DB erreichbar, sonst 503.
    """
    start = time.monotonic()
    db_ok = False
    db_error = None

    try:
        connection.ensure_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db_ok = True
    except Exception as exc:
        db_error = str(exc)

    duration_ms = round((time.monotonic() - start) * 1000, 2)
    status = 200 if db_ok else 503

    payload = {
        "status": "ok" if db_ok else "error",
        "checks": {
            "database": {
                "status": "ok" if db_ok else "error",
                "response_time_ms": duration_ms,
            }
        },
    }
    if db_error:
        payload["checks"]["database"]["error"] = db_error

    return JsonResponse(payload, status=status)
