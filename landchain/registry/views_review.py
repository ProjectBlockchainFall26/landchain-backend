"""Stub views. Each returns 501 until its task is built. Owners are in the docstrings."""
from rest_framework.views import APIView

from landchain.core.stubs import not_implemented


class ReviewQueueView(APIView):
    """
    GET /api/v1/review/queue  [IsOfficer]
        Task D7 (Person D): Review queue and nav badge counts
        Spec: docs/api-spec.md section 9.10 · Postman: 'GET /review/queue'
        The three cards of the Review Queue, with a hint for items the caller's role cannot act
    on ("Only the registrar can act").
    """

    def get(self, request, *args, **kwargs):
        # TODO(D7): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("D7", request)


class ReviewCountsView(APIView):
    """
    GET /api/v1/review/counts  [IsOfficer]
        Task D7 (Person D): Review queue and nav badge counts
        Spec: docs/api-spec.md section 9.10 · Postman: 'GET /review/counts'
        Badge in the nav: items the caller can act on (pendingCountFor). Identity officer counts
    identities; registrar counts applications + transfers.
    """

    def get(self, request, *args, **kwargs):
        # TODO(D7): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("D7", request)

