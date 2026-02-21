"""
OpenTelemetry bootstrap für Traces (Tempo), Metrics (Prometheus) und Logs (Loki).

Wird in manage.py und wsgi.py vor dem Django-Start aufgerufen.
Aktiviert wird es über die Umgebungsvariable OTEL_ENABLED=true.
"""

import logging
import os

logger = logging.getLogger(__name__)


def configure_opentelemetry() -> None:
    """Konfiguriert OpenTelemetry Tracing, Metrics und Logging."""
    otel_enabled = os.environ.get("OTEL_ENABLED", "false").lower() == "true"
    if not otel_enabled:
        logger.debug("OpenTelemetry deaktiviert (OTEL_ENABLED != true)")
        return

    _configure_tracing()
    _configure_metrics()
    _configure_loki_logging()
    _instrument_django()

    logger.info("OpenTelemetry vollständig konfiguriert")


def _configure_tracing() -> None:
    """Traces → Tempo via OTLP/gRPC."""
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION

    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    if not endpoint:
        logger.warning(
            "OTEL_EXPORTER_OTLP_ENDPOINT nicht gesetzt – Traces werden verworfen"
        )
        return

    resource = Resource.create(
        {
            SERVICE_NAME: os.environ.get("OTEL_SERVICE_NAME", "djangotestproject"),
            SERVICE_VERSION: os.environ.get("OTEL_SERVICE_VERSION", "0.1.0"),
            "deployment.environment": os.environ.get("ENVIRONMENT", "production"),
        }
    )

    provider = TracerProvider(resource=resource)

    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )

        exporter = OTLPSpanExporter(endpoint=endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        logger.info("Trace-Exporter (OTLP/gRPC) → %s", endpoint)
    except Exception as exc:
        logger.error("Trace-Exporter konnte nicht initialisiert werden: %s", exc)

    trace.set_tracer_provider(provider)


def _configure_metrics() -> None:
    """Metrics → Prometheus Scrape-Endpoint (via django-prometheus).

    Zusätzlich können Metrics per OTLP an einen OTEL Collector gepusht werden,
    falls OTEL_METRICS_EXPORTER=otlp gesetzt ist.
    """
    exporter_type = os.environ.get("OTEL_METRICS_EXPORTER", "prometheus").lower()
    if exporter_type != "otlp":
        # django-prometheus übernimmt das Prometheus-Scraping
        logger.info("Metrics: Prometheus-Scraping via django-prometheus (/metrics)")
        return

    from opentelemetry import metrics
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME

    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    if not endpoint:
        return

    try:
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
            OTLPMetricExporter,
        )

        exporter = OTLPMetricExporter(endpoint=endpoint)
        reader = PeriodicExportingMetricReader(exporter, export_interval_millis=15000)
        provider = MeterProvider(
            resource=Resource.create(
                {SERVICE_NAME: os.environ.get("OTEL_SERVICE_NAME", "djangotestproject")}
            ),
            metric_readers=[reader],
        )
        metrics.set_meter_provider(provider)
        logger.info("Metrics-Exporter (OTLP/gRPC) → %s", endpoint)
    except Exception as exc:
        logger.error("Metrics-Exporter konnte nicht initialisiert werden: %s", exc)


def _configure_loki_logging() -> None:
    """Structured Logs → Loki via python-logging-loki."""
    loki_url = os.environ.get("LOKI_URL", "")
    if not loki_url:
        logger.debug("LOKI_URL nicht gesetzt – Loki-Handler nicht aktiviert")
        return

    try:
        import logging_loki

        handler = logging_loki.LokiHandler(
            url=loki_url,
            tags={
                "app": os.environ.get("OTEL_SERVICE_NAME", "djangotestproject"),
                "environment": os.environ.get("ENVIRONMENT", "production"),
            },
            auth=(
                os.environ.get("LOKI_USERNAME", ""),
                os.environ.get("LOKI_PASSWORD", ""),
            )
            if os.environ.get("LOKI_USERNAME")
            else None,
            version="1",
        )
        handler.setLevel(logging.INFO)

        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        logger.info("Loki-Handler aktiviert → %s", loki_url)
    except Exception as exc:
        logger.error("Loki-Handler konnte nicht initialisiert werden: %s", exc)


def _instrument_django() -> None:
    """Auto-Instrumentierung für Django, DB und HTTP-Clients."""
    try:
        from opentelemetry.instrumentation.django import DjangoInstrumentor

        DjangoInstrumentor().instrument()
        logger.debug("Django-Instrumentierung aktiv")
    except Exception as exc:
        logger.warning("Django-Instrumentierung fehlgeschlagen: %s", exc)

    try:
        from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor

        Psycopg2Instrumentor().instrument()
        logger.debug("Psycopg2-Instrumentierung aktiv")
    except Exception as exc:
        logger.warning("Psycopg2-Instrumentierung fehlgeschlagen: %s", exc)

    try:
        from opentelemetry.instrumentation.requests import RequestsInstrumentor

        RequestsInstrumentor().instrument()
        logger.debug("Requests-Instrumentierung aktiv")
    except Exception as exc:
        logger.warning("Requests-Instrumentierung fehlgeschlagen: %s", exc)

    try:
        from opentelemetry.instrumentation.logging import LoggingInstrumentor

        LoggingInstrumentor().instrument(set_logging_format=True)
        logger.debug("Logging-Instrumentierung aktiv (trace_id in Logs)")
    except Exception as exc:
        logger.warning("Logging-Instrumentierung fehlgeschlagen: %s", exc)
