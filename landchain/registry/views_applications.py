"""Stub views. Each returns 501 until its task is built. Owners are in the docstrings."""
from rest_framework.views import APIView

from landchain.core.stubs import not_implemented


class ApplicationsView(APIView):
    """
    POST /api/v1/applications  [IsVerifiedCitizen, TitleRegistry.submitApplication]
        Task D5 (Person D): Applications: submit, list, review, approve, reject
        Spec: docs/api-spec.md section 9.6 · Postman: 'POST /applications'
        Prepares the application transaction from the Register Land form. The server converts
    degrees to micro-degrees, computes acresX100, uppercases plan number and GPS address,
    and puts the staged documents' types and fingerprints in docs (file names stay off
    chain).

    GET /api/v1/applications  [IsSignedIn]
        Task D5 (Person D): Applications: submit, list, review, approve, reject
        Spec: docs/api-spec.md section 9.6 · Postman: 'GET /applications'
        Officers see all; citizens see their own.
    """

    def post(self, request, *args, **kwargs):
        # TODO(D5): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("D5", request)

    def get(self, request, *args, **kwargs):
        # TODO(D5): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("D5", request)


class ApplicationsDetailView(APIView):
    """
    GET /api/v1/applications/{id}  [IsOfficer or applicant]
        Task D5 (Person D): Applications: submit, list, review, approve, reject
        Spec: docs/api-spec.md section 9.6 · Postman: 'GET /applications/{id}'
        Review dialog: application, parcel detail (map, plan number, pillars, documents with
    can_open), and the fee checklist.
    """

    def get(self, request, *args, **kwargs):
        # TODO(D5): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("D5", request)


class ApplicationsDetailApproveView(APIView):
    """
    POST /api/v1/applications/{id}/approve  [IsRegistrar, TitleRegistry.approveApplication]
        Task D5 (Person D): Applications: submit, list, review, approve, reject
        Spec: docs/api-spec.md section 9.6 · Postman: 'POST /applications/{id}/approve'
        Mints the title NFT to the applicant. Signed by the registrar role wallet.
    """

    def post(self, request, *args, **kwargs):
        # TODO(D5): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("D5", request)


class ApplicationsDetailRejectView(APIView):
    """
    POST /api/v1/applications/{id}/reject  [IsRegistrar, TitleRegistry.rejectApplication]
        Task D5 (Person D): Applications: submit, list, review, approve, reject
        Spec: docs/api-spec.md section 9.6 · Postman: 'POST /applications/{id}/reject'
        The reason goes on chain (public). Tell officers in the UI not to put personal data in
    it.
    """

    def post(self, request, *args, **kwargs):
        # TODO(D5): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("D5", request)

