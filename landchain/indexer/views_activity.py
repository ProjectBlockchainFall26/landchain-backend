"""Stub views. Each returns 501 until its task is built. Owners are in the docstrings."""
from rest_framework.views import APIView

from landchain.core.stubs import not_implemented


class ActivityView(APIView):
    """
    GET /api/v1/activity  [Public (names filtered)]
        Task C7 (Person C): Activity log `GET /activity`
        Spec: docs/api-spec.md section 9.12 · Postman: 'GET /activity'
        Every contract call, newest first, including refused simulations (RevertLog) and wallet
    cancellations. Now shared by everyone, where today reverts are kept per browser.
    """

    def get(self, request, *args, **kwargs):
        # TODO(C7): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("C7", request)

