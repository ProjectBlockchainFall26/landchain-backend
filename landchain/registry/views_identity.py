"""Stub views. Each returns 501 until its task is built. Owners are in the docstrings."""
from rest_framework.views import APIView

from landchain.core.stubs import not_implemented


class IdentitySubmitView(APIView):
    """
    POST /api/v1/identity/submit  [HasWallet · citizen, IdentityRegistry.submitProfile]
        Task B8 (Person B): Identity endpoints (submit, list, lookup, verify, reject)
        Spec: docs/api-spec.md section 9.3 · Postman: 'POST /identity/submit'
        Prepares the citizen's submitProfile(cardHash, citizen) transaction. The card number is
    hashed in the browser (hashCard) and only the hash is sent, as today. Also allowed after
    a rejection (resubmit).
    """

    def post(self, request, *args, **kwargs):
        # TODO(B8): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("B8", request)


class IdentitiesView(APIView):
    """
    GET /api/v1/identities  [IsOfficer]
        Task B8 (Person B): Identity endpoints (submit, list, lookup, verify, reject)
        Spec: docs/api-spec.md section 9.3 · Postman: 'GET /identities'
        People with an on-chain profile. Default filter is the identity queue.
    """

    def get(self, request, *args, **kwargs):
        # TODO(B8): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("B8", request)


class IdentitiesLookupView(APIView):
    """
    GET /api/v1/identities/lookup  [IsSignedIn]
        Task B8 (Person B): Identity endpoints (submit, list, lookup, verify, reject)
        Spec: docs/api-spec.md section 9.3 · Postman: 'GET /identities/lookup'
        Used by the Transfer dialog: the owner types the buyer's public ID and sees only whether
    they can receive a title (PROJECT_CONTEXT P1 #7). No name is returned.
    """

    def get(self, request, *args, **kwargs):
        # TODO(B8): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("B8", request)


class IdentitiesDetailVerifyView(APIView):
    """
    POST /api/v1/identities/{public_id}/verify  [IsIdentityOfficer, IdentityRegistry.verifyProfile]
        Task B8 (Person B): Identity endpoints (submit, list, lookup, verify, reject)
        Spec: docs/api-spec.md section 9.3 · Postman: 'POST /identities/{public_id}/verify'
        Signed by the identity-officer role wallet.
    """

    def post(self, request, *args, **kwargs):
        # TODO(B8): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("B8", request)


class IdentitiesDetailRejectView(APIView):
    """
    POST /api/v1/identities/{public_id}/reject  [IsIdentityOfficer, IdentityRegistry.rejectProfile]
        Task B8 (Person B): Identity endpoints (submit, list, lookup, verify, reject)
        Spec: docs/api-spec.md section 9.3 · Postman: 'POST /identities/{public_id}/reject'
        Same as verify. The contract takes no reason; the optional reason is stored off chain
    and sent in the notification.
    """

    def post(self, request, *args, **kwargs):
        # TODO(B8): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("B8", request)

