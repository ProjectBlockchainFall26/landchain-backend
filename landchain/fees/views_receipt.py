"""Statement of costs GET /parcels/{parcel_id}/receipt (task C9, spec 9.12). Replaces chain/gas.ts."""
from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from rest_framework.response import Response
from rest_framework.views import APIView

from landchain.chain.encoding import acres_str, iso
from landchain.core import privacy
from landchain.core.errors import Private
from landchain.core.permissions import Public, viewer
from landchain.indexer.models import ChainTx
from landchain.registry.selectors import current_parcel
from landchain.registry.serializers import ctx_for

from .models import Payment
from .serializers import payment_obj, payments_total
from .views import PRIVATE_MSG

LABELS = {"submitApplication": "Application", "approveApplication": "Registration",
          "rejectApplication": "Registration rejected", "requestTransfer": "Transfer request",
          "cancelTransfer": "Transfer cancelled", "approveTransfer": "Transfer", "rejectTransfer": "Transfer rejected"}


def _label(tx: ChainTx) -> str:
    if tx.function == "recordPayment":
        kind = tx.args_label.split(", ", 1)[-1] if ", " in tx.args_label else "fee"
        return f"Record {kind.lower()} receipt" if kind != "First registration" else "Record registration fee receipt"
    return LABELS.get(tx.function, tx.function)


def _eth(wei) -> str:
    return f"{Decimal(wei) / Decimal(10**18):.6f}"


class ParcelsDetailReceiptView(APIView):
    """GET /api/v1/parcels/{parcel_id}/receipt [canSeePrivate]."""

    permission_classes = [Public]

    def get(self, request, parcel_id, *args, **kwargs):
        from landchain.chain.views import chain_name
        p = current_parcel(parcel_id)
        me = viewer(request)
        if not privacy.can_see_private(me, p):
            raise Private(PRIVATE_MSG.format(pid=p.parcel_id))
        ctx = ctx_for(request)
        pays = list(Payment.objects.filter(record_id=p.record_id).order_by("payment_id"))
        txs = [t for t in ChainTx.objects.filter(record_ids__contains=[p.record_id]).order_by("block_number",
                                                                                              "tx_index")]
        owners = {o.address for o in p.owners.all()} | {p.owner_address, p.applicant_address}
        items, total, owner_total = [], 0, 0
        for t in txs:
            cost = int(t.cost_wei)
            total += cost
            if t.from_address in owners:
                owner_total += cost
            items.append({"label": _label(t), "tx_hash": t.tx_hash,
                          "signed_by": privacy.person_ref(me, t.from_public_id, ctx.people), "block": t.block_number,
                          "gas_used": t.gas_used,
                          "gas_price_gwei": f"{Decimal(t.effective_gas_price_wei) / Decimal(10**9):g}",
                          "cost_eth": _eth(cost), "at": iso(t.at)})
        name = chain_name()
        notes = ([f"On {name} this is test ETH with no real value. Officer transactions are paid by the Lands "
                  "Commission's own wallet."] if settings.CHAIN_ID != 1 else
                 ["Officer transactions are paid by the Lands Commission's own wallet."])
        notes.append("Fee amounts are what the registrar recorded from the official receipts.")
        return Response({
            "parcel": {"parcel_id": p.parcel_id, "title_no": p.token_id or None, "owner": ctx.ref(p.owner_public_id),
                       "plan_number": p.plan_number, "acres": acres_str(p.acres_x100), "interest": p.interest_name,
                       "location": p.location},
            "fees": {"total_ghs": payments_total(pays),
                     "items": [payment_obj(x, me, ctx.people, p.parcel_id) for x in pays]},
            "transactions": {"items": items, "total_eth": _eth(total), "owner_signed_eth": _eth(owner_total)},
            "chain_name": name, "notes": notes,
        })
