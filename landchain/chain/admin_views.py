"""Stub views. Each returns 501 until its task is built. Owners are in the docstrings."""
from rest_framework.views import APIView

from landchain.core.stubs import not_implemented


class AdminChainRolesView(APIView):
    """
    POST /api/v1/admin/chain/roles  [IsAdmin, LandAccessControl.grantRole / revokeRole]
        Task B7 (Person B): Admin chain tools: role wallets and signer health
        Spec: docs/api-spec.md section 9.13 · Postman: 'POST /admin/chain/roles'
        Rotate a role wallet on chain (e.g. new registrar key). Signed by the admin wallet.
    """

    def post(self, request, *args, **kwargs):
        # TODO(B7): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("B7", request)


class AdminSignersView(APIView):
    """
    GET /api/v1/admin/signers  [IsAdmin]
        Task B7 (Person B): Admin chain tools: role wallets and signer health
        Spec: docs/api-spec.md section 9.13 · Postman: 'GET /admin/signers'
    """

    def get(self, request, *args, **kwargs):
        # TODO(B7): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("B7", request)

