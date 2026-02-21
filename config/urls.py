from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", include("apps.health.urls")),
    path("", include("django_prometheus.urls")),  # /metrics endpoint
]
