"""Payment shape (spec 8). Receipt numbers only for officers (privacy.can_see_receipt_numbers)."""
from __future__ import annotations

from landchain.chain.encoding import ghs_str, iso
from landchain.core import privacy

from .models import Payment, PaymentReceipt
from .schedule import FEE_INFO


def payment_obj(p: Payment, viewer, people=None, parcel_id: str | None = None) -> dict:
    receipt_no = None
    if privacy.can_see_receipt_numbers(viewer):
        r = PaymentReceipt.objects.filter(payment_id=p.payment_id).first() or \
            PaymentReceipt.objects.filter(receipt_hash=p.receipt_hash).first()
        receipt_no = r.receipt_no if r else None
    if parcel_id is None:
        from landchain.registry.models import Parcel
        parcel_id = Parcel.objects.filter(record_id=p.record_id).values_list("parcel_id", flat=True).first()
    return {
        "id": f"PAY-{p.payment_id}", "payment_id": p.payment_id, "parcel_id": parcel_id, "record_id": p.record_id,
        "kind": p.kind_name, "kind_index": p.kind, "paid_to": FEE_INFO[p.kind_name]["paid_to"],
        "amount_ghs": ghs_str(p.amount_pesewas), "amount_pesewas": p.amount_pesewas,
        "receipt_hash": p.receipt_hash, "receipt_no": receipt_no,
        "payer": privacy.person_ref_for_address(viewer, p.payer_address, people),
        "recorded_by": privacy.person_ref_for_address(viewer, p.recorded_by, people),
        "transfer_id": f"TRF-{p.transfer_id}" if p.transfer_id else None,
        "at": iso(p.at), "block": p.block_number or None, "tx_hash": p.tx_hash or None,
    }


def payments_total(payments) -> str:
    return ghs_str(sum(p.amount_pesewas for p in payments))
