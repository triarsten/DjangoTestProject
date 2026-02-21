import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# OTel MUSS vor Django initialisiert werden
from config.telemetry import configure_opentelemetry

configure_opentelemetry()

application = get_wsgi_application()
