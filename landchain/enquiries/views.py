"""Stub views. Each returns 501 until its task is built. Owners are in the docstrings."""
from rest_framework.views import APIView

from landchain.core.stubs import not_implemented


class ParcelsDetailEnquiriesView(APIView):
    """
    POST /api/v1/parcels/{parcel_id}/enquiries  [Public]
        Task A8 (Person A): Enquiries: send, owner inbox, mark read/answered
        Spec: docs/api-spec.md section 9.11 · Postman: 'POST /parcels/{parcel_id}/enquiries'
        "Enquire about this land". Goes to the current owner without revealing them. Not allowed
    on rejected parcels, by officers, or by the owner themself.
    """

    def post(self, request, *args, **kwargs):
        # TODO(A8): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("A8", request)


class MeEnquiriesView(APIView):
    """
    GET /api/v1/me/enquiries  [IsSignedIn]
        Task A8 (Person A): Enquiries: send, owner inbox, mark read/answered
        Spec: docs/api-spec.md section 9.11 · Postman: 'GET /me/enquiries'
        The owner's inbox (Enquiries section on the title record). Only enquiries addressed to
    my public ID.
    """

    def get(self, request, *args, **kwargs):
        # TODO(A8): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("A8", request)


class EnquiriesDetailView(APIView):
    """
    PATCH /api/v1/enquiries/{id}  [recipient]
        Task A8 (Person A): Enquiries: send, owner inbox, mark read/answered
        Spec: docs/api-spec.md section 9.11 · Postman: 'PATCH /enquiries/{id}'
        Replaces markEnquiry (read on hover, "Mark as answered").
    """

    def patch(self, request, *args, **kwargs):
        # TODO(A8): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("A8", request)

