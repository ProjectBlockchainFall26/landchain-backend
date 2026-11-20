"""Stub views. Each returns 501 until its task is built. Owners are in the docstrings."""
from rest_framework.views import APIView

from landchain.core.stubs import not_implemented


class HealthView(APIView):
    """
    GET /api/v1/health  [Public]
        Task B1 (Person B): Error format, ID helpers, health check, Celery + Redis
        Spec: docs/api-spec.md section 9.1 · Postman: 'GET /health'
        Liveness for the load balancer. Checks database and Redis, not the chain.
    """

    def get(self, request, *args, **kwargs):
        # TODO(B1): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("B1", request)

