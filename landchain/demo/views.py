"""Stub views. Each returns 501 until its task is built. Owners are in the docstrings."""
from rest_framework.views import APIView

from landchain.core.stubs import not_implemented


class DevDemoAccountsView(APIView):
    """
    GET /api/v1/dev/demo-accounts  [Public · local chain only]
        Task A6 (Person A): Demo users: `seed_demo_users` + `/dev/demo-accounts`
        Spec: docs/api-spec.md section 9.1 · Postman: 'GET /dev/demo-accounts'
        Lists the seeded Supabase demo users so the login page can offer one-click sign-in.
    Returns 404 unless CHAIN_ID=1337 and DEMO_MODE=true.
    """

    def get(self, request, *args, **kwargs):
        # TODO(A6): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("A6", request)

