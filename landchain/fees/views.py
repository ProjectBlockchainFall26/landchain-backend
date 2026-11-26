"""Fee schedule and estimates (task D3) and payments (task D4). Spec 9.7."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.db import transaction
from rest_framework.response import Response
from rest_framework.views import APIView

from landchain.chain import service
from landchain.chain.encoding import FEE_KINDS, fee_kind_index, pesewas, receipt_hash
from landchain.chain.views import intent_response
from landchain.core import privacy
from landchain.core.errors import Private, Validation
from landchain.core.idempotency import idempotent
from landchain.core.ids import parse_id
from landchain.core.permissions import IsRegistrar, Public, viewer
from landchain.registry.selectors import current_parcel, open_transfer
from landchain.registry.serializers import ctx_for

from .models import Payment, PaymentReceipt
from .schedule import estimate, schedule
from .serializers import payment_obj, payments_total

PRIVATE_MSG = "Receipts are private. Only the owner and the Lands Commission can see what was paid for {pid}."


def _dec(v, field) -> Decimal | None:
    if v in (None, ""):
        return None
    try:
        d = Decimal(str(v))
    except InvalidOperation:
        raise Validation(f"{field} must be a number", field_errors={field: ["Must be a number"]}) from None
    if d < 0:
        raise Validation(f"{field} can't be negative", field_errors={field: ["Can't be negative"]})
    return d


def _kind(raw) -> str:
    try:
        return FEE_KINDS[fee_kind_index(raw)]
    except ValueError:
        raise Validation("Unknown fee kind", field_errors={"kind": [f"Use one of: {', '.join(FEE_KINDS)}"]}) from None


class FeesScheduleView(APIView):
    """GET /api/v1/fees/schedule [Public]."""

    permission_classes = [Public]

    def get(self, request, *args, **kwargs):
        return Response(schedule())


class FeesEstimateView(APIView):
    """GET /api/v1/fees/estimate?kind=&acres=|parcel_id=&consideration= [Public]."""

    permission_classes = [Public]

    def get(self, request, *args, **kwargs):
        q = request.query_params
        kind = _kind(q.get("kind", ""))
        acres = _dec(q.get("acres"), "acres")
        if q.get("parcel_id"):
            acres = Decimal(current_parcel(q["parcel_id"]).acres_x100) / 100
        return Response(estimate(kind, float(acres or 0), _dec(q.get("consideration"), "consideration")))


class ParcelsDetailPaymentsView(APIView):
    """GET [canSeePrivate] and POST [IsRegistrar] /api/v1/parcels/{parcel_id}/payments."""

    forbidden_message = "Only the registrar can record a payment"

    def get_permissions(self):
        return [IsRegistrar()] if self.request.method == "POST" else [Public()]

    def get(self, request, parcel_id, *args, **kwargs):
        p = current_parcel(parcel_id)
        me = viewer(request)
        if not privacy.can_see_private(me, p):
            raise Private(PRIVATE_MSG.format(pid=p.parcel_id))
        ctx = ctx_for(request)
        pays = list(Payment.objects.filter(record_id=p.record_id).order_by("payment_id"))
        return Response({"parcel_id": p.parcel_id, "total_ghs": payments_total(pays),
                         "results": [payment_obj(x, me, ctx.people, p.parcel_id) for x in pays]})

    @idempotent
    def post(self, request, parcel_id, *args, **kwargs):
        d = request.data
        p = current_parcel(parcel_id, missing=f"Parcel {parcel_id.upper()} does not exist")
        kind = _kind(d.get("kind") if d.get("kind") is not None else d.get("kind_index", ""))
        receipt_no = str(d.get("receipt_no") or "").strip()
        if not receipt_no:
            raise Validation("Add the official receipt number",
                             field_errors={"receipt_no": ["Add the official receipt number"]})
        if len(receipt_no) > 64:
            raise Validation("Receipt number is too long", field_errors={"receipt_no": ["At most 64 characters"]})
        consideration = _dec(d.get("consideration_ghs"), "consideration_ghs")
        amount = _dec(d.get("amount_ghs"), "amount_ghs")
        if amount is None:
            sug = estimate(kind, p.acres_x100 / 100, consideration)["suggested_ghs"]
            amount = Decimal(sug) if sug else None
        if not amount or amount <= 0:
            raise Validation("Amount must be greater than zero",
                             field_errors={"amount_ghs": ["Amount must be greater than zero"]})
        if kind == "Transfer" and d.get("transfer_id"):
            want = parse_id(d["transfer_id"], "TRF", what="Transfer")
            ot = open_transfer(p)
            if ot is None or ot.transfer_id != want:
                raise Validation("There is no transfer waiting for this parcel",
                                 field_errors={"transfer_id": ["Must be the parcel's open transfer"]})
        rhash = receipt_hash(receipt_no)
        with transaction.atomic():
            intent = service.write(
                signer="registrar", contract="FeeLedger", function="recordPayment",
                args=[p.record_id, fee_kind_index(kind), pesewas(amount), rhash],
                label=f"\"{p.parcel_id}\", {kind}", success=f"{kind} receipt recorded", by=viewer(request),
                target=p.parcel_id, note=d.get("note"), request=request,
                idempotency_key=request.headers.get("Idempotency-Key"))
            PaymentReceipt.objects.get_or_create(intent=intent, defaults={
                "receipt_hash": rhash, "receipt_no": receipt_no.upper(), "consideration_ghs": consideration,
                "note": d.get("note") or None})

        def then():
            pay = Payment.objects.filter(receipt_hash=rhash).first()
            ctx = ctx_for(request)
            return {"payment": payment_obj(pay, ctx.viewer, ctx.people, p.parcel_id) if pay else None}
        return intent_response(request, intent, then=then)
