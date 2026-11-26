"""Transfers: request, cancel, review, approve, reject (task D6, spec 9.8)."""
from __future__ import annotations

import re

from rest_framework.response import Response
from rest_framework.views import APIView

from landchain.chain import client, service
from landchain.chain.views import intent_response
from landchain.core.errors import NotFound, Validation
from landchain.core.idempotency import idempotent
from landchain.core.ids import parse_id
from landchain.core.pagination import paginate
from landchain.core.permissions import HasWallet, IsRegistrar, IsSignedIn, IsVerifiedCitizen, viewer
from landchain.core.ratelimit import limit

from .models import TransferRequest
from .selectors import address_for_public_id, current_parcel
from .serializers import ctx_for, parcel_detail, transfer_fee_recorded, transfer_obj
from .views_applications import fee_checklist

DECISIONS = ["waiting", "approved", "rejected", "cancelled"]
REMINDER = ("Check the signed indenture before approving. Approving moves the title NFT to the new owner and adds "
            "them to the on-chain owner history.")


def _transfer(id_) -> TransferRequest:
    t = TransferRequest.objects.select_related("parcel").filter(
        transfer_id=parse_id(id_, "TRF", what="Transfer")).first()
    if t is None:
        raise NotFound("Transfer not found")
    return t


class TransfersView(APIView):
    """POST /api/v1/transfers [IsVerifiedCitizen · owner] and GET /api/v1/transfers [IsSignedIn]."""

    identity_message = "Verify your identity before transferring land"

    def get_permissions(self):
        return [IsVerifiedCitizen()] if self.request.method == "POST" else [IsSignedIn()]

    @idempotent
    def post(self, request, *args, **kwargs):
        limit(request, "prepare")
        pid = str(request.data.get("parcel_id") or "").strip()
        to = str(request.data.get("to_public_id") or "").strip()
        if not pid:
            raise Validation("Pick the parcel", field_errors={"parcel_id": ["Pick the parcel"]})
        if not re.fullmatch(r"GH-[0-9a-fA-F]{8}", to):
            raise NotFound("Pick the new owner")
        parcel = current_parcel(pid, missing="Parcel does not exist")
        to_addr = address_for_public_id(to)
        if to_addr is None:
            raise NotFound("Pick the new owner")
        intent = service.prepare(
            profile=viewer(request), contract="TitleRegistry", function="requestTransfer",
            args=[parcel.record_id, client.checksum(to_addr)], label=f"\"{parcel.parcel_id}\", GH-{to[3:].lower()}",
            success="Transfer requested: waiting for the registrar",
            idempotency_key=request.headers.get("Idempotency-Key"))
        return intent_response(request, intent, created=True)

    def get(self, request, *args, **kwargs):
        me, q = viewer(request), request.query_params
        qs = TransferRequest.objects.select_related("parcel").order_by("-transfer_id")
        if not me.is_officer:
            pid = me.public_id or "-"
            role = q.get("role")
            if role == "from":
                qs = qs.filter(from_public_id=pid)
            elif role == "to":
                qs = qs.filter(to_public_id=pid)
            else:
                from django.db.models import Q
                qs = qs.filter(Q(from_public_id=pid) | Q(to_public_id=pid))
        if q.get("decision"):
            names = [x.strip() for x in q["decision"].split(",")]
            if any(n not in DECISIONS for n in names):
                raise Validation("Unknown decision", field_errors={"decision": [f"Use {', '.join(DECISIONS)}"]})
            qs = qs.filter(decision__in=[DECISIONS.index(n) for n in names])
        if q.get("parcel_id"):
            qs = qs.filter(parcel__parcel_id=q["parcel_id"].strip().upper())
        ctx = ctx_for(request)
        return paginate(request, qs, lambda t: transfer_obj(t, ctx), view=self)


class TransfersDetailCancelView(APIView):
    """POST /api/v1/transfers/{id}/cancel [HasWallet · requester]."""

    permission_classes = [HasWallet]

    @idempotent
    def post(self, request, id, *args, **kwargs):
        t = _transfer(id)
        intent = service.prepare(
            profile=viewer(request), contract="TitleRegistry", function="cancelTransfer", args=[t.transfer_id],
            label=f"TRF-{t.transfer_id}", success="Transfer cancelled",
            idempotency_key=request.headers.get("Idempotency-Key"))
        return intent_response(request, intent, created=True)


class TransfersDetailView(APIView):
    """GET /api/v1/transfers/{id} [IsOfficer, from or to]: the transfer review dialog."""

    permission_classes = [IsSignedIn]

    def get(self, request, id, *args, **kwargs):
        t = _transfer(id)
        me = viewer(request)
        if not me.is_officer and me.public_id not in (t.from_public_id, t.to_public_id):
            raise NotFound("Transfer not found")
        ctx = ctx_for(request)
        obj = transfer_obj(t, ctx)
        fee = transfer_fee_recorded(t)
        blocked = None
        if t.decision != 0:
            blocked = "This transfer has already been decided"
        elif not fee:
            blocked = "Record the transfer fee before approving"
        elif obj["to_identity"] != "verified":
            blocked = "The new owner must have a verified identity"
        elif not me.is_registrar:
            blocked = "Only the registrar can approve a transfer"
        return Response({"transfer": obj, "parcel": parcel_detail(t.parcel, ctx),
                         "fee_checklist": fee_checklist(t.parcel, ctx, kinds=("Transfer",),
                                                        transfer_id=t.transfer_id),
                         "can_approve": blocked is None, "blocked_reason": blocked, "reminder": REMINDER})


class TransfersDetailApproveView(APIView):
    """POST /api/v1/transfers/{id}/approve [IsRegistrar]."""

    permission_classes = [IsRegistrar]
    forbidden_message = "Only the registrar can approve a transfer"

    @idempotent
    def post(self, request, id, *args, **kwargs):
        t = _transfer(id)
        intent = service.write(
            signer="registrar", contract="TitleRegistry", function="approveTransfer", args=[t.transfer_id],
            label=f"TRF-{t.transfer_id}", success="Transfer approved: title moved to the new owner",
            by=viewer(request), target=f"TRF-{t.transfer_id}", note=request.data.get("note"), request=request,
            idempotency_key=request.headers.get("Idempotency-Key"))

        def then():
            t.parcel.refresh_from_db()
            return {"parcel": parcel_detail(t.parcel, ctx_for(request))}
        return intent_response(request, intent, then=then)


class TransfersDetailRejectView(APIView):
    """POST /api/v1/transfers/{id}/reject [IsRegistrar]. The reason is public on chain."""

    permission_classes = [IsRegistrar]
    forbidden_message = "Only the registrar can reject a transfer"

    @idempotent
    def post(self, request, id, *args, **kwargs):
        reason = str(request.data.get("reason") or "").strip()
        if not reason or len(reason) > 280:
            raise Validation("A reason is required to reject",
                             field_errors={"reason": ["A reason (1 to 280 characters) is required to reject"]})
        t = _transfer(id)
        intent = service.write(
            signer="registrar", contract="TitleRegistry", function="rejectTransfer", args=[t.transfer_id, reason],
            label=f"TRF-{t.transfer_id}, \"{reason}\"", success="Transfer rejected", by=viewer(request),
            target=f"TRF-{t.transfer_id}", note=reason, request=request,
            idempotency_key=request.headers.get("Idempotency-Key"))

        def then():
            t.parcel.refresh_from_db()
            return {"parcel": parcel_detail(t.parcel, ctx_for(request))}
        return intent_response(request, intent, then=then)
