"""GET /health (task B1, spec 9.1). Checks the database and Redis, not the chain."""
from django.conf import settings
from django.core.cache import cache
from django.db import connection
from rest_framework.response import Response
from rest_framework.views import APIView

from landchain.core.permissions import Public


class HealthView(APIView):
    permission_classes = [Public]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        db = redis = "ok"
        try:
            with connection.cursor() as c:
                c.execute("SELECT 1")
        except Exception:
            db = "error"
        try:
            cache.set("health:ping", 1, 5)
            if cache.get("health:ping") != 1:
                redis = "error"
        except Exception:
            redis = "error"
        ok = db == "ok" and redis == "ok"
        return Response({"ok": ok, "version": settings.API_VERSION, "db": db, "redis": redis},
                        status=200 if ok else 503)
