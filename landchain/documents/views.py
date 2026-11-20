"""Stub views. Each returns 501 until its task is built. Owners are in the docstrings."""
from rest_framework.views import APIView

from landchain.core.stubs import not_implemented


class DocumentsView(APIView):
    """
    POST /api/v1/documents  [HasWallet]
        Task D2 (Person D): Document vault (Supabase Storage)
        Spec: docs/api-spec.md section 9.4 · Postman: 'POST /documents'
        Upload one document before submitting an application. Django computes SHA-256 itself,
    stores the file at parcel-documents/<sha256> (content-addressed, so the same file
    uploaded twice is stored once), and returns the fingerprint to put on chain. Replaces
    putFile, which today runs after submission; uploading first means the file is never
    lost.
    """

    def post(self, request, *args, **kwargs):
        # TODO(D2): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("D2", request)


class DocumentsDetailUrlView(APIView):
    """
    GET /api/v1/documents/{sha256}/url  [canSeePrivate for a parcel holding this fingerprint]
        Task D2 (Person D): Document vault (Supabase Storage)
        Spec: docs/api-spec.md section 9.4 · Postman: 'GET /documents/{sha256}/url'
        Signed URL to open a file (the "Open" buttons in the title record and review dialog).
    Replaces openFile.
    """

    def get(self, request, *args, **kwargs):
        # TODO(D2): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("D2", request)


class ParcelsDetailDocumentsCheckView(APIView):
    """
    POST /api/v1/parcels/{parcel_id}/documents/check  [Public]
        Task D2 (Person D): Document vault (Supabase Storage)
        Spec: docs/api-spec.md section 9.4 · Postman: 'POST /parcels/{parcel_id}/documents/check'
        "Have a copy? Check it against the register." Hashing can stay in the browser (send only
    the hash, so the file never leaves the visitor's device); a multipart file is also
    accepted.
    """

    def post(self, request, *args, **kwargs):
        # TODO(D2): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("D2", request)

