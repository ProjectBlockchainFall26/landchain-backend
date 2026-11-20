"""Stub views. Each returns 501 until its task is built. Owners are in the docstrings."""
from rest_framework.views import APIView

from landchain.core.stubs import not_implemented


class FeesScheduleView(APIView):
    """
    GET /api/v1/fees/schedule  [Public]
        Task D3 (Person D): Fee schedule and estimates
        Spec: docs/api-spec.md section 9.7 · Postman: 'GET /fees/schedule'
        From fees.ts. Estimates only; the source text must be shown.
    """

    def get(self, request, *args, **kwargs):
        # TODO(D3): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("D3", request)


class FeesEstimateView(APIView):
    """
    GET /api/v1/fees/estimate  [Public]
        Task D3 (Person D): Fee schedule and estimates
        Spec: docs/api-spec.md section 9.7 · Postman: 'GET /fees/estimate'
        Suggested amount. Rules: search 163; stamp duty = round(price × rate), rate 0.25% if
    price ≤ 10,000, 0.5% if < 50,000, else 1%; first registration 1,178 × max(1,
    ceil(acres)); transfer 973 × max(1, ceil(acres)).
    """

    def get(self, request, *args, **kwargs):
        # TODO(D3): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("D3", request)


class ParcelsDetailPaymentsView(APIView):
    """
    GET /api/v1/parcels/{parcel_id}/payments  [canSeePrivate]
        Task D4 (Person D): Payments: record and list fees
        Spec: docs/api-spec.md section 9.7 · Postman: 'GET /parcels/{parcel_id}/payments'

    POST /api/v1/parcels/{parcel_id}/payments  [IsRegistrar, FeeLedger.recordPayment]
        Task D4 (Person D): Payments: record and list fees
        Spec: docs/api-spec.md section 9.7 · Postman: 'POST /parcels/{parcel_id}/payments'
        The registrar records an official receipt from the Review Queue fee recorder. The
    receipt number is hashed (keccak256 of the trimmed, uppercased number) and the plain
    number is kept in PaymentReceipt. For Transfer, the contract binds the fee to the
    parcel's open transfer.
    """

    def get(self, request, *args, **kwargs):
        # TODO(D4): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("D4", request)

    def post(self, request, *args, **kwargs):
        # TODO(D4): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("D4", request)

