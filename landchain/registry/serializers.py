"""Parcel, Application, TransferRequest and HistoryEvent shapes (spec 8). Privacy through core.privacy only."""
from __future__ import annotations

from django.conf import settings

from landchain.chain import contracts as reg
from landchain.chain.encoding import PARCEL_STATUS_LABEL, acres_str, iso
from landchain.core import privacy
from landchain.fees.models import Payment
from landchain.fees.schedule import REGISTRATION_REQUIRED

from .geo import centroid
from .models import Application, HistoryEvent, Parcel, TransferRequest

EXPLORERS = {11155111: "https://sepolia.etherscan.io"}


class Ctx:
    """Per-request context: the viewer and a PeopleIndex cache."""

    def __init__(self, viewer):
        self.viewer = viewer
        self.people = privacy.PeopleIndex()

    def ref(self, public_id):
        return privacy.person_ref(self.viewer, public_id, self.people)

    def ref_addr(self, address):
        return privacy.person_ref_for_address(self.viewer, address, self.people)


def ctx_for(request) -> Ctx:
    from landchain.core.permissions import viewer
    return Ctx(viewer(request))


def _title_address() -> str | None:
    try:
        return reg.deployment().address("TitleRegistry")
    except reg.ContractsMissing:
        return None


def parcel_list_item(p: Parcel, ctx: Ctx, *, owners_count: int | None = None) -> dict:
    pillars = p.pillars
    owners = list(p.owners.all())
    status = p.status_name
    return {
        "parcel_id": p.parcel_id, "record_id": p.record_id, "title_no": p.token_id or None,
        "status": status, "status_label": PARCEL_STATUS_LABEL[status],
        "interest": p.interest_name, "holder": p.holder, "region": p.region, "location": p.location,
        "plan_number": p.plan_number, "gps_address": p.gps_address or None,
        "acres": acres_str(p.acres_x100), "acres_x100": p.acres_x100,
        "owner": ctx.ref(p.owner_public_id),
        "owners": [ctx.ref(o.public_id) for o in owners],
        "owners_count": owners_count if owners_count is not None else len(owners),
        "boundary": {"pillars": pillars, "centroid": centroid(pillars) if pillars else None,
                     "pillar_count": len(pillars)},
        "registered_at": iso(p.registered_at), "updated_at": iso(p.updated_at),
    }


def fees_summary(p: Parcel) -> dict:
    pays = list(Payment.objects.filter(record_id=p.record_id))
    kinds = {x.kind_name for x in pays}
    return {"total_ghs": f"{sum(x.amount_pesewas for x in pays) / 100:.2f}", "count": len(pays),
            "stamp_duty_recorded": "Stamp duty" in kinds, "first_registration_recorded": "First registration" in kinds,
            "official_search_recorded": "Official search" in kinds}


def missing_registration_fees(record_id: int) -> list[str]:
    from landchain.chain.encoding import FEE_KINDS
    kinds = {FEE_KINDS[k] for k in Payment.objects.filter(record_id=record_id).values_list("kind", flat=True)}
    return [k for k in REGISTRATION_REQUIRED if k not in kinds]


def viewer_flags(p: Parcel, ctx: Ctx, open_trf: TransferRequest | None) -> dict:
    v = ctx.viewer
    pid = getattr(v, "public_id", None)
    is_owner = bool(pid and pid == p.owner_public_id and p.status in (1, 2))
    was_owner = bool(pid and not is_owner and p.owners.filter(public_id=pid).exists())
    from landchain.core.permissions import chain_identity_status
    verified = bool(v and not v.is_officer and chain_identity_status(v) == "verified")
    return {
        "is_owner": is_owner, "was_owner": was_owner,
        "can_transfer": bool(is_owner and verified and p.status == 1 and open_trf is None),
        "can_cancel_transfer": bool(open_trf and pid and open_trf.from_public_id == pid),
        "can_enquire": bool(p.status != 3 and not (v and v.is_officer) and not is_owner),
    }


def document_rows(p: Parcel, ctx: Ctx, private: bool) -> list[dict]:
    from landchain.documents.service import available_hashes
    docs = list(p.docs.all())
    have = available_hashes(d.sha256 for d in docs)
    return [{"doc_type": d.doc_type, "sha256": d.sha256, "file_available": d.sha256 in have,
             "can_open": bool(private and d.sha256 in have)} for d in docs]


def parcel_detail(p: Parcel, ctx: Ctx) -> dict:
    from .selectors import latest_application, open_transfer
    private = privacy.can_see_private(ctx.viewer, p)
    out = parcel_list_item(p, ctx)
    out.pop("owners_count", None)
    out["boundary"].update(lats_micro=p.lats_micro, lngs_micro=p.lngs_micro)
    app = latest_application(p)
    trf = open_transfer(p) if p.status == 2 else None
    out["documents"] = document_rows(p, ctx, private)
    out["application"] = ({
        "id": f"APP-{app.app_id}", "decision": app.decision_name, "applicant": ctx.ref(app.applicant_public_id),
        "created_at": iso(app.created_at), "decided_by": ctx.ref_addr(app.decided_by) if app.decided_by else None,
        "decided_at": iso(app.decided_at), "reason": app.reason or None} if app else None)
    out["open_transfer"] = transfer_obj(trf, ctx, parcel=p) if trf else None
    out["fees"] = fees_summary(p) if private else None
    out["visibility"] = "private" if private else "public"
    out["viewer"] = viewer_flags(p, ctx, trf)
    addr = _title_address()
    explorer = EXPLORERS.get(settings.CHAIN_ID)
    out["chain"] = {"chain_id": settings.CHAIN_ID, "contract": "TitleRegistry", "address": addr,
                    "record_id": p.record_id, "token_id": p.token_id or None,
                    "explorer_url": (f"{explorer}/token/{addr}?a={p.token_id}" if explorer and p.token_id else None)}
    return out


def application_obj(a: Application, ctx: Ctx, *, parcel: Parcel | None = None) -> dict:
    parcel = parcel or a.parcel
    missing = missing_registration_fees(parcel.record_id)
    return {"id": f"APP-{a.app_id}", "app_id": a.app_id, "parcel_id": parcel.parcel_id, "record_id": parcel.record_id,
            "applicant": ctx.ref(a.applicant_public_id), "created_at": iso(a.created_at),
            "decision": a.decision_name, "decided_by": ctx.ref_addr(a.decided_by) if a.decided_by else None,
            "decided_at": iso(a.decided_at), "reason": a.reason or None,
            "fees_ready": not missing, "missing_fees": missing}


def transfer_fee_recorded(t: TransferRequest) -> bool:
    return Payment.objects.filter(transfer_id=t.transfer_id, kind=3).exists()


def transfer_obj(t: TransferRequest, ctx: Ctx, *, parcel: Parcel | None = None) -> dict:
    from .selectors import identity_of
    parcel = parcel or t.parcel
    to_id = identity_of(t.to_address)
    return {"id": f"TRF-{t.transfer_id}", "transfer_id": t.transfer_id, "parcel_id": parcel.parcel_id,
            "record_id": parcel.record_id, "from": ctx.ref(t.from_public_id), "to": ctx.ref(t.to_public_id),
            "to_identity": to_id.status_name if to_id else "none", "requested_at": iso(t.requested_at),
            "decision": t.decision_name, "decided_by": ctx.ref_addr(t.decided_by) if t.decided_by else None,
            "decided_at": iso(t.decided_at), "reason": t.reason or None,
            "transfer_fee_recorded": transfer_fee_recorded(t)}


def history_obj(h: HistoryEvent) -> dict:
    return {"parcel_id": h.parcel_id, "type": h.type, "text": h.text, "at": iso(h.at), "block": h.block_number,
            "tx_hash": h.tx_hash}
