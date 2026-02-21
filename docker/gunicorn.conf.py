"""
Gunicorn Konfiguration.
Werte können per Umgebungsvariable überschrieben werden (siehe entrypoint.sh).
Diese Datei dient als Dokumentation der verfügbaren Optionen.
"""

import multiprocessing
import os

# Binding
bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"

# Worker
workers = int(os.environ.get("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))
worker_class = os.environ.get("GUNICORN_WORKER_CLASS", "sync")
worker_tmp_dir = "/dev/shm"  # Shared Memory für Worker-Heartbeat (kein I/O-Wait)

# Timeouts
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "30"))
graceful_timeout = int(os.environ.get("GUNICORN_GRACEFUL_TIMEOUT", "20"))
keepalive = int(os.environ.get("GUNICORN_KEEP_ALIVE", "5"))

# Recycling (Speicherlecks vermeiden)
max_requests = int(os.environ.get("GUNICORN_MAX_REQUESTS", "1000"))
max_requests_jitter = int(os.environ.get("GUNICORN_MAX_REQUESTS_JITTER", "100"))

# Logging
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")
accesslog = "-"  # stdout
errorlog = "-"  # stderr
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)sus'

# Prozess-Name
proc_name = "djangotestproject"


# =============================================================================
# Server Hooks
# =============================================================================


def post_fork(_server, worker):
    """
    Wird in jedem Worker-Prozess nach dem Fork aufgerufen.

    OpenTelemetry muss pro Worker neu initialisiert werden, da der Master-Prozess
    geforkt wird: TracerProvider, SDK-Threads und gRPC-Verbindungen sind nicht
    fork-safe und würden sonst zwischen Workers geteilt werden.
    """
    import logging

    logger = logging.getLogger("gunicorn.error")

    try:
        from config.telemetry import configure_opentelemetry

        configure_opentelemetry()
        logger.info("[worker %s] OpenTelemetry initialisiert", worker.pid)
    except Exception as exc:
        logger.warning(
            "[worker %s] OpenTelemetry-Initialisierung fehlgeschlagen: %s",
            worker.pid,
            exc,
        )


def worker_exit(_server, worker):  # pyright: ignore[reportUnusedParameter]
    """
    Wird aufgerufen bevor ein Worker-Prozess beendet wird (SIGQUIT/SIGTERM).

    Flusht ausstehende Spans und Metrics damit keine Telemetrie-Daten verloren gehen.
    """
    import logging

    logger = logging.getLogger("gunicorn.error")

    try:
        from opentelemetry import metrics, trace

        # Traces flushen
        tracer_provider = trace.get_tracer_provider()
        if hasattr(tracer_provider, "force_flush"):
            tracer_provider.force_flush(timeout_millis=5000)

        # Metrics flushen
        meter_provider = metrics.get_meter_provider()
        if hasattr(meter_provider, "force_flush"):
            meter_provider.force_flush(timeout_millis=5000)

        logger.info("[worker %s] OpenTelemetry sauber heruntergefahren", worker.pid)
    except Exception as exc:
        logger.warning("[worker %s] OpenTelemetry-Shutdown fehlgeschlagen: %s", worker.pid, exc)
