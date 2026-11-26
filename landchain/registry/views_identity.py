"""Identity endpoints (task B8, spec 9.3): IdentityRegistry.submitProfile / verifyProfile / rejectProfile."""
from __future__ import annotations

import re

from django.db.models import Q
from rest_framework.response import Response
from rest_framework.views import APIView

from landchain.chain import client, service
from landchain.chain.encoding import IDENTITY_STATUS, ZERO_HASH, iso
from landchain.chain.views import intent_response
from landchain.core.errors import NotFound, Validation
from landchain.core.idempotency import idempotent
from landchain.core.pagination import paginate
from landchain.core.permissions import HasWallet, IsIdentityOfficer, IsOfficer, IsSignedIn, viewer
from landchain.core.ratelimit import limit

from .models import ChainIdentity
from .selectors import address_for_public_id


def _pid(raw: str) -> str:
    return "GH-" + (raw or "").strip()[3:].lower()


class IdentitySubmitView(APIView):
    """POST /api/v1/identity/submit [HasWallet · citizen]. Prepares submitProfile(cardHash, citizen)."""

    permission_classes = [HasWallet]

    @idempotent
    def post(self, request, *args, **kwargs):
        limit(request, "prepare")
        p = viewer(request)
        card_hash = str(request.data.get("card_hash", "")).strip().lower()
        citizenship = str(request.data.get("citizenship", "citizen")).strip().lower()
        fe = {}
        if not re.fullmatch(r"0x[0-9a-f]{64}", card_hash) or card_hash == ZERO_HASH:
            fe["card_hash"] = ["Card hash is empty"]
        if citizenship not in ("citizen", "non-citizen"):
            fe["citizenship"] = ["Use citizen or non-citizen"]
        if fe:
            raise Validation(next(iter(fe.values()))[0], field_errors=fe)
        name = request.data.get("full_name")
        if name is not None:
            name = str(name).strip()
            if not 2 <= len(name) <= 120:
                raise Validation("Name must be 2 to 120 characters",
                                 field_errors={"full_name": ["Name must be 2 to 120 characters"]})
            p.full_name = name
            p.save(update_fields=["full_name", "updated_at"])
        intent = service.prepare(
            profile=p, contract="IdentityRegistry", function="submitProfile",
            args=[card_hash, citizenship == "citizen"], label=f"{card_hash[:10]}…, {citizenship}",
            success="Identity submitted: waiting for the identity officer",
            idempotency_key=request.headers.get("Idempotency-Key"))
        return intent_response(request, intent, created=True)


class IdentitiesView(APIView):
    """GET /api/v1/identities [IsOfficer]. Default filter is the identity queue (?status=pending)."""

    permission_classes = [IsOfficer]

    def get(self, request, *args, **kwargs):
        from landchain.accounts.models import Profile
        status = request.query_params.get("status", "pending")
        if status not in IDENTITY_STATUS:
            raise Validation("Unknown status", field_errors={"status": [f"Use {', '.join(IDENTITY_STATUS)}"]})
        qs = ChainIdentity.objects.filter(status=IDENTITY_STATUS.index(status)).order_by("submitted_at", "address")
        q = (request.query_params.get("q") or "").strip()
        if q:
            addrs = Profile.objects.filter(full_name__icontains=q).values_list("wallet_address", flat=True)
            qs = qs.filter(Q(public_id__icontains=q.lower()) | Q(address__in=list(addrs)))
        profiles = {p.wallet_address: p for p in Profile.objects.filter(
            wallet_address__in=list(qs.values_list("address", flat=True)))}

        def row(ci):
            p = profiles.get(ci.address)
            return {"public_id": ci.public_id, "name": (p.full_name or None) if p else None, "address": ci.address,
                    "status": ci.status_name, "citizenship": "citizen" if ci.citizen else "non-citizen",
                    "card_hash": ci.card_hash, "submitted_at": iso(ci.submitted_at),
                    "email": p.email if p else None, "phone": p.phone if p else None}
        return paginate(request, qs, row, view=self)


class IdentitiesLookupView(APIView):
    """GET /api/v1/identities/lookup?public_id= [IsSignedIn]. Decision 18.7: always 200 with exists."""

    permission_classes = [IsSignedIn]

    def get(self, request, *args, **kwargs):
        raw = request.query_params.get("public_id", "")
        if not re.fullmatch(r"GH-[0-9a-fA-F]{8}", raw.strip()):
            raise Validation("A public ID looks like GH-9c2a41d0",
                             field_errors={"public_id": ["A public ID looks like GH-9c2a41d0"]})
        pid = _pid(raw)
        me = viewer(request)
        ci = ChainIdentity.objects.filter(public_id=pid).first()
        exists = ci is not None or address_for_public_id(pid) is not None
        return Response({"public_id": pid, "exists": exists, "verified": bool(ci and ci.status == 2),
                         "is_you": me.public_id == pid})


def _officer_identity_action(request, public_id: str, *, verify: bool):
    pid = _pid(public_id)
    ci = ChainIdentity.objects.filter(public_id=pid).first()
    address = ci.address if ci else address_for_public_id(pid)
    if address is None:
        raise NotFound(f"No person with public ID {pid}.")
    fn = "verifyProfile" if verify else "rejectProfile"
    note = str(request.data.get("note" if verify else "reason") or "").strip() or None
    intent = service.write(
        signer="id_officer", contract="IdentityRegistry", function=fn, args=[client.checksum(address)], label=pid,
        success="Identity verified" if verify else "Identity rejected", by=viewer(request), target=pid, note=note,
        request=request, idempotency_key=request.headers.get("Idempotency-Key"))

    def then():
        ci2 = ChainIdentity.objects.filter(public_id=pid).first()
        return {"identity": {"public_id": pid, "status": ci2.status_name if ci2 else "none"}}
    return intent_response(request, intent, then=then)


class IdentitiesDetailVerifyView(APIView):
    """POST /api/v1/identities/{public_id}/verify [IsIdentityOfficer]."""

    permission_classes = [IsIdentityOfficer]

    @idempotent
    def post(self, request, public_id, *args, **kwargs):
        return _officer_identity_action(request, public_id, verify=True)


class IdentitiesDetailRejectView(APIView):
    """POST /api/v1/identities/{public_id}/reject [IsIdentityOfficer]."""

    permission_classes = [IsIdentityOfficer]

    @idempotent
    def post(self, request, public_id, *args, **kwargs):
        return _officer_identity_action(request, public_id, verify=False)
