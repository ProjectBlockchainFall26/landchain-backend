"""Stub views. Each returns 501 until its task is built. Owners are in the docstrings."""
from rest_framework.views import APIView

from landchain.core.stubs import not_implemented


class AdminIndexerResyncView(APIView):
    """
    POST /api/v1/admin/indexer/resync  [IsAdmin]
        Task C4 (Person C): Reorg / fresh-chain handling + `POST /admin/indexer/resync`
        Spec: docs/api-spec.md section 9.13 · Postman: 'POST /admin/indexer/resync'
        Wipe the projection for the current chain and re-index from startBlock. Use after npm
    run chain:fresh + setup:all.
    """

    def post(self, request, *args, **kwargs):
        # TODO(C4): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("C4", request)

