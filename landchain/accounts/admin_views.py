"""Stub views. Each returns 501 until its task is built. Owners are in the docstrings."""
from rest_framework.views import APIView

from landchain.core.stubs import not_implemented


class AdminOfficersView(APIView):
    """
    GET /api/v1/admin/officers  [IsAdmin]
        Task A5 (Person A): Officer management (admin)
        Spec: docs/api-spec.md section 9.13 · Postman: 'GET /admin/officers'

    POST /api/v1/admin/officers  [IsAdmin]
        Task A5 (Person A): Officer management (admin)
        Spec: docs/api-spec.md section 9.13 · Postman: 'POST /admin/officers'
        Give a Supabase user an officer role. Off chain only: the person acts through the role
    wallet. Syncs app_metadata.landchain_roles.
    """

    def get(self, request, *args, **kwargs):
        # TODO(A5): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("A5", request)

    def post(self, request, *args, **kwargs):
        # TODO(A5): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("A5", request)


class AdminOfficersDetailView(APIView):
    """
    DELETE /api/v1/admin/officers/{user_id}  [IsAdmin]
        Task A5 (Person A): Officer management (admin)
        Spec: docs/api-spec.md section 9.13 · Postman: 'DELETE /admin/officers/{user_id}'
        Removes all officer roles. ?role=registrar removes one. Returns 204.
    """

    def delete(self, request, *args, **kwargs):
        # TODO(A5): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("A5", request)

