from django.core.exceptions import DisallowedHost


class HealthCheckMiddleware:
    """
    Leitet /health/ direkt an die Health-View weiter, bevor SecurityMiddleware
    den ALLOWED_HOSTS-Check durchführt.

    Hintergrund: Django's SecurityMiddleware prüft den HTTP Host-Header in
    process_request() und wirft DisallowedHost, wenn der Host nicht in
    ALLOWED_HOSTS steht. Das passiert bevor die View aufgerufen wird – die
    View kann die Exception daher nicht selbst abfangen.

    Diese Middleware sitzt direkt vor SecurityMiddleware und ruft die
    Health-View bei /health/ auf, ohne den Host-Header zu validieren.
    Das ist für K8s-Liveness/Readiness-Probes notwendig, da kubelet Anfragen
    mit der Pod-IP als Host-Header schickt, die nicht in ALLOWED_HOSTS steht.
    """

    HEALTH_PATH = "/health/"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == self.HEALTH_PATH:
            try:
                from .views import health

                return health(request)
            except DisallowedHost:
                # Sollte durch den direkten View-Aufruf nicht auftreten,
                # aber als Fallback falls die View intern get_host() aufruft.
                from .views import health

                return health(request)

        return self.get_response(request)
