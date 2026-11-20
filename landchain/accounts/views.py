"""Stub views. Each returns 501 until its task is built. Owners are in the docstrings."""
from rest_framework.views import APIView

from landchain.core.stubs import not_implemented


class MeView(APIView):
    """
    GET /api/v1/me  [IsSignedIn]
        Task A3 (Person A): `GET /me` and `PATCH /me`
        Spec: docs/api-spec.md section 9.2 · Postman: 'GET /me'
        The signed-in person. Replaces useMe(). Creates the profile on first call.

    PATCH /api/v1/me  [IsSignedIn]
        Task A3 (Person A): `GET /me` and `PATCH /me`
        Spec: docs/api-spec.md section 9.2 · Postman: 'PATCH /me'
        Edit off-chain profile details. Replaces setMyName.
    """

    def get(self, request, *args, **kwargs):
        # TODO(A3): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("A3", request)

    def patch(self, request, *args, **kwargs):
        # TODO(A3): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("A3", request)


class AuthWalletNonceView(APIView):
    """
    POST /api/v1/auth/wallet/nonce  [IsSignedIn]
        Task A4 (Person A): Wallet linking with Sign-In with Ethereum
        Spec: docs/api-spec.md section 9.2 · Postman: 'POST /auth/wallet/nonce'
    """

    def post(self, request, *args, **kwargs):
        # TODO(A4): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("A4", request)


class AuthWalletVerifyView(APIView):
    """
    POST /api/v1/auth/wallet/verify  [IsSignedIn]
        Task A4 (Person A): Wallet linking with Sign-In with Ethereum
        Spec: docs/api-spec.md section 9.2 · Postman: 'POST /auth/wallet/verify'
        Checks the personal_sign signature and links the address.
    """

    def post(self, request, *args, **kwargs):
        # TODO(A4): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("A4", request)

