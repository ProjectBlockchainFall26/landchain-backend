"""Stub views. Each returns 501 until its task is built. Owners are in the docstrings."""
from rest_framework.views import APIView

from landchain.core.stubs import not_implemented


class MeNotificationsView(APIView):
    """
    GET /api/v1/me/notifications  [IsSignedIn]
        Task A7 (Person A): Notifications: models, inbox endpoints and email/SMS relay
        Spec: docs/api-spec.md section 9.2 · Postman: 'GET /me/notifications'
        Notifications addressed to my public ID, plus those addressed to each of my roles
    (role:Registrar, role:Identity officer), plus new enquiries about my parcels (text "New
    enquiry about GA-BRK-0003 from Kojo Appiah. Open the title to read it."). Newest first.
    """

    def get(self, request, *args, **kwargs):
        # TODO(A7): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("A7", request)


class MeNotificationsReadView(APIView):
    """
    POST /api/v1/me/notifications/read  [IsSignedIn]
        Task A7 (Person A): Notifications: models, inbox endpoints and email/SMS relay
        Spec: docs/api-spec.md section 9.2 · Postman: 'POST /me/notifications/read'
    """

    def post(self, request, *args, **kwargs):
        # TODO(A7): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("A7", request)

