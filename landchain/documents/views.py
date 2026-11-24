"""Document vault (task D2, spec 9.4)."""
from __future__ import annotations

import re

from django.db import IntegrityError, transaction
from rest_framework.response import Response
from rest_framework.views import APIView

from landchain.chain.encoding import file_fingerprint, iso
from landchain.core import privacy
from landchain.core.errors import ApiError, NotFound, Private, Validation
from landchain.core.permissions import HasWallet, Public, viewer
from landchain.core.ratelimit import limit
from landchain.registry.models import ParcelDoc
from landchain.registry.selectors import current_parcel

from . import storage
from .models import ALLOWED_MIME, DOC_TYPE_NAMES, Document
from .service import file_for

MAX_BYTES = 20 * 1024 * 1024
MAGIC = {b"%PDF": "application/pdf", b"\xff\xd8\xff": "image/jpeg", b"\x89PNG": "image/png"}


def _sniff(data: bytes) -> str | None:
    for sig, mime in MAGIC.items():
        if data.startswith(sig):
            return mime
    return None


def doc_obj(d: Document) -> dict:
    return {"id": d.id, "sha256": d.sha256, "doc_type": d.doc_type, "name": d.original_name, "mime": d.mime,
            "size_bytes": d.size_bytes, "status": d.status, "created_at": iso(d.created_at)}


class DocumentsView(APIView):
    """POST /api/v1/documents [HasWallet] (multipart: file, doc_type, sha256?)."""

    permission_classes = [HasWallet]

    def post(self, request, *args, **kwargs):
        f = request.FILES.get("file")
        doc_type = str(request.data.get("doc_type") or "").strip()
        if doc_type not in DOC_TYPE_NAMES:
            raise Validation("Unknown document type", field_errors={"doc_type": [f"Use one of: {', '.join(DOC_TYPE_NAMES)}"]})
        if f is None or f.size == 0:
            raise Validation("The file is empty", field_errors={"file": ["Choose a file"]})
        if f.size > MAX_BYTES:
            raise ApiError("Files can be at most 20 MB.", code="FILE_TOO_LARGE", status_code=413)
        data = f.read()
        mime = _sniff(data)
        if mime is None or mime not in ALLOWED_MIME:
            raise ApiError("Upload a PDF, JPEG or PNG file.", code="UNSUPPORTED_MEDIA_TYPE", status_code=415)
        sha = file_fingerprint(data)
        claimed = str(request.data.get("sha256") or "").strip().lower()
        if claimed and claimed != sha:
            raise ApiError("The file's fingerprint doesn't match the one your browser computed. Upload it again.",
                           code="HASH_MISMATCH", status_code=422)
        storage.put(sha, data, mime)
        me = viewer(request)
        try:
            with transaction.atomic():
                d = Document.objects.create(sha256=sha, doc_type=doc_type, original_name=(f.name or "file")[:255],
                                            mime=mime, size_bytes=len(data), storage_path=sha, uploaded_by=me)
        except IntegrityError:
            d = Document.objects.get(sha256=sha, uploaded_by=me)
            if d.status != Document.Status.ATTACHED and d.doc_type != doc_type:
                d.doc_type = doc_type
                d.save(update_fields=["doc_type"])
        return Response(doc_obj(d), status=201)


class DocumentsDetailUrlView(APIView):
    """GET /api/v1/documents/{sha256}/url?parcel_id= [canSeePrivate for that parcel]."""

    permission_classes = [Public]

    def get(self, request, sha256, *args, **kwargs):
        sha = sha256.lower()
        pid = request.query_params.get("parcel_id")
        if not pid:
            raise Validation("parcel_id is required", field_errors={"parcel_id": ["Which parcel holds this file?"]})
        p = current_parcel(pid)
        doc = ParcelDoc.objects.filter(parcel=p, sha256=sha).first()
        if doc is None:
            raise NotFound("This fingerprint isn't registered for this parcel.")
        if not privacy.can_see_private(viewer(request), p):
            raise Private("Files are held by the Lands Commission. Only their fingerprints are public.")
        f = file_for(sha, p.record_id)
        if f is None or not storage.exists(f.storage_path):
            raise ApiError("This file isn't in the vault. Seeded demo parcels have fingerprints only.",
                           code="FILE_NOT_IN_VAULT", status_code=404)
        return Response({"url": storage.signed_url(f.storage_path, name=f.original_name, mime=f.mime, request=request),
                         "expires_in": storage.SIGNED_URL_TTL, "name": f.original_name, "mime": f.mime,
                         "doc_type": doc.doc_type})


class ParcelsDetailDocumentsCheckView(APIView):
    """POST /api/v1/parcels/{parcel_id}/documents/check [Public]: {"sha256"} or multipart file."""

    permission_classes = [Public]

    def post(self, request, parcel_id, *args, **kwargs):
        limit(request, "document_check")
        p = current_parcel(parcel_id)
        f = request.FILES.get("file") if hasattr(request, "FILES") else None
        if f is not None:
            if f.size > MAX_BYTES:
                raise ApiError("Files can be at most 20 MB.", code="FILE_TOO_LARGE", status_code=413)
            sha = file_fingerprint(f.read())
        else:
            sha = str(request.data.get("sha256") or "").strip().lower()
            if not re.fullmatch(r"0x[0-9a-f]{64}", sha):
                raise Validation("sha256 is 0x followed by 64 hex characters",
                                 field_errors={"sha256": ["Use 0x followed by 64 hex characters"]})
        doc = ParcelDoc.objects.filter(parcel=p, sha256=sha).first()
        if doc:
            return Response({"match": True, "doc_type": doc.doc_type,
                             "message": f"This file matches the registered {doc.doc_type}. It hasn't been changed."})
        return Response({"match": False, "doc_type": None,
                         "message": "This file doesn't match any document registered for this parcel."})
