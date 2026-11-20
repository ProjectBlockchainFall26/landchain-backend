"""Stub views. Each returns 501 until its task is built. Owners are in the docstrings."""
from rest_framework.views import APIView

from landchain.core.stubs import not_implemented


class ParcelsDetailReceiptView(APIView):
    """
    GET /api/v1/parcels/{parcel_id}/receipt  [canSeePrivate]
        Task C9 (Person C): Statement of costs `GET /parcels/{parcel_id}/receipt`
        Spec: docs/api-spec.md section 9.12 · Postman: 'GET /parcels/{parcel_id}/receipt'
        Statement of costs. One row per distinct transaction on the parcel (an approval that
    also mints is one row). Gas comes from stored receipts (replaces chain/gas.ts).
    """

    def get(self, request, *args, **kwargs):
        # TODO(C9): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("C9", request)

