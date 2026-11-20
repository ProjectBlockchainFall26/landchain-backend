"""Stub views. Each returns 501 until its task is built. Owners are in the docstrings."""
from rest_framework.views import APIView

from landchain.core.stubs import not_implemented


class TransfersView(APIView):
    """
    POST /api/v1/transfers  [IsVerifiedCitizen · owner, TitleRegistry.requestTransfer]
        Task D6 (Person D): Transfers: request, cancel, review, approve, reject
        Spec: docs/api-spec.md section 9.8 · Postman: 'POST /transfers'
        The owner asks to record a new owner (sale or gift agreed off the platform). The buyer
    is given by public ID; the server resolves the address.

    GET /api/v1/transfers  [IsSignedIn]
        Task D6 (Person D): Transfers: request, cancel, review, approve, reject
        Spec: docs/api-spec.md section 9.8 · Postman: 'GET /transfers'
        Officers see all; citizens see transfers where they are from or to.
    """

    def post(self, request, *args, **kwargs):
        # TODO(D6): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("D6", request)

    def get(self, request, *args, **kwargs):
        # TODO(D6): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("D6", request)


class TransfersDetailCancelView(APIView):
    """
    POST /api/v1/transfers/{id}/cancel  [HasWallet · requester, TitleRegistry.cancelTransfer]
        Task D6 (Person D): Transfers: request, cancel, review, approve, reject
        Spec: docs/api-spec.md section 9.8 · Postman: 'POST /transfers/{id}/cancel'
    """

    def post(self, request, *args, **kwargs):
        # TODO(D6): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("D6", request)


class TransfersDetailView(APIView):
    """
    GET /api/v1/transfers/{id}  [IsOfficer, from or to]
        Task D6 (Person D): Transfers: request, cancel, review, approve, reject
        Spec: docs/api-spec.md section 9.8 · Postman: 'GET /transfers/{id}'
        Transfer review dialog.
    """

    def get(self, request, *args, **kwargs):
        # TODO(D6): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("D6", request)


class TransfersDetailApproveView(APIView):
    """
    POST /api/v1/transfers/{id}/approve  [IsRegistrar, TitleRegistry.approveTransfer]
        Task D6 (Person D): Transfers: request, cancel, review, approve, reject
        Spec: docs/api-spec.md section 9.8 · Postman: 'POST /transfers/{id}/approve'
    """

    def post(self, request, *args, **kwargs):
        # TODO(D6): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("D6", request)


class TransfersDetailRejectView(APIView):
    """
    POST /api/v1/transfers/{id}/reject  [IsRegistrar, TitleRegistry.rejectTransfer]
        Task D6 (Person D): Transfers: request, cancel, review, approve, reject
        Spec: docs/api-spec.md section 9.8 · Postman: 'POST /transfers/{id}/reject'
    """

    def post(self, request, *args, **kwargs):
        # TODO(D6): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("D6", request)

