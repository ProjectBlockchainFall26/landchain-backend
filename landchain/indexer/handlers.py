"""One handler per contract event (task C3, mapping table in spec 6.5), plus the side effects of C8.

Handlers record what an event touched; `refresh_*` then copies the contract's current state from its view
functions, so the projection always equals the contract. History lines, activity labels and notifications use
the same texts as the frontend's snapshot.ts.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from django.contrib.gis.geos import LinearRing, Polygon
from django.db.models import Max

from landchain.chain import client
from landchain.chain.encoding import (
    FEE_KINDS,
    cedi,
    hex0x,
    public_id,
    ts_to_dt,
)
from landchain.fees.models import Payment, PaymentReceipt
from landchain.registry.models import (
    Application,
    ChainIdentity,
    ChainRole,
    HistoryEvent,
    OwnerHistory,
    Parcel,
    ParcelDoc,
    TransferRequest,
)

log = logging.getLogger("landchain.indexer")

ROLE_NAMES = {"REGISTRAR_ROLE": "registrar", "ID_OFFICER_ROLE": "id_officer", "DEFAULT_ADMIN_ROLE": "admin"}


@dataclass
class EventCtx:
    contract: str
    event: str
    args: dict
    block: int
    log_index: int
    tx_hash: str
    at: object  # datetime
    chain_event: object  # ChainEvent row


@dataclass
class Pass:
    """What one indexer pass touched (refreshed at the end of each event)."""

    records: set = field(default_factory=set)
    labels: dict = field(default_factory=dict)       # tx_hash -> (function, args_label, record_ids)


# ---------------------------------------------------------------- refresh from view functions
def _titles():
    return client.contract("TitleRegistry")


def refresh_identity(address: str, *, submitted_at=None):
    address = address.lower()
    status, citizen, card, updated = client.contract("IdentityRegistry").functions.profileOf(
        client.checksum(address)).call()
    defaults = {"public_id": public_id(address), "status": int(status), "citizen": bool(citizen),
                "card_hash": hex0x(card), "updated_at": ts_to_dt(updated)}
    if submitted_at is not None:
        defaults["submitted_at"] = submitted_at
    ChainIdentity.objects.update_or_create(address=address, defaults=defaults)


def refresh_roles():
    acl = client.contract("LandAccessControl")
    rows = []
    for const, name in ROLE_NAMES.items():
        role_id = acl.functions[const]().call()
        for i in range(acl.functions.getRoleMemberCount(role_id).call()):
            rows.append((acl.functions.getRoleMember(role_id, i).call().lower(), name))
    ChainRole.objects.all().delete()
    ChainRole.objects.bulk_create([ChainRole(address=a, role=r) for a, r in rows])


def _polygon(lats, lngs):
    if len(lats) < 3:
        return None
    pts = [(lng / 1e6, lat / 1e6) for lat, lng in zip(lats, lngs, strict=False)]
    pts.append(pts[0])
    try:
        return Polygon(LinearRing(pts), srid=4326)
    except Exception:
        return None


def refresh_record(record_id: int, block: int) -> Parcel:
    t = _titles()
    (pid, interest, holder, region, location, plan, gps, acres, status, owner, token, reg_at, upd_at) = \
        t.functions.getParcel(record_id).call()
    lats, lngs = t.functions.getBoundary(record_id).call()
    docs = t.functions.getDocs(record_id).call()
    owners = t.functions.ownerHistory(record_id).call()
    owner = owner.lower()
    parcel, created = Parcel.objects.update_or_create(record_id=record_id, defaults={
        "parcel_id": pid, "interest": int(interest), "holder": holder, "region": region, "location": location,
        "plan_number": plan, "gps_address": gps, "acres_x100": int(acres), "status": int(status),
        "owner_address": owner, "owner_public_id": public_id(owner), "token_id": int(token) or None,
        "registered_at": ts_to_dt(reg_at), "updated_at": ts_to_dt(upd_at), "lats_micro": [int(x) for x in lats],
        "lngs_micro": [int(x) for x in lngs], "boundary": _polygon(lats, lngs), "updated_block": block})
    if created:
        Parcel.objects.filter(pk=record_id).update(created_block=block)
    ParcelDoc.objects.filter(parcel=parcel).delete()
    ParcelDoc.objects.bulk_create([ParcelDoc(parcel=parcel, position=i, doc_type=d[0], sha256=hex0x(d[1]))
                                   for i, d in enumerate(docs)])
    OwnerHistory.objects.filter(parcel=parcel).delete()
    OwnerHistory.objects.bulk_create([OwnerHistory(parcel=parcel, position=i, address=a.lower(),
                                                   public_id=public_id(a)) for i, a in enumerate(owners)])
    mark_current(pid)
    return parcel


def mark_current(parcel_id: str):
    latest = Parcel.objects.filter(parcel_id=parcel_id).aggregate(m=Max("record_id"))["m"]
    Parcel.objects.filter(parcel_id=parcel_id).exclude(record_id=latest).update(is_current=False)
    Parcel.objects.filter(record_id=latest).update(is_current=True)


def refresh_application(app_id: int):
    rec, applicant, created, decision, by, at, reason = _titles().functions.getApplication(app_id).call()
    applicant = applicant.lower()
    Application.objects.update_or_create(app_id=app_id, defaults={
        "parcel_id": int(rec), "applicant_address": applicant, "applicant_public_id": public_id(applicant),
        "created_at": ts_to_dt(created), "decision": int(decision), "decided_by": by.lower() if int(at) else "",
        "decided_at": ts_to_dt(at), "reason": reason})
    Parcel.objects.filter(record_id=int(rec)).update(applicant_address=applicant,
                                                      applicant_public_id=public_id(applicant))


def refresh_transfer(transfer_id: int):
    rec, frm, to, req, decision, by, at, reason = _titles().functions.getTransfer(transfer_id).call()
    TransferRequest.objects.update_or_create(transfer_id=transfer_id, defaults={
        "parcel_id": int(rec), "from_address": frm.lower(), "from_public_id": public_id(frm),
        "to_address": to.lower(), "to_public_id": public_id(to), "requested_at": ts_to_dt(req),
        "decision": int(decision), "decided_by": by.lower() if int(at) else "", "decided_at": ts_to_dt(at),
        "reason": reason})


def refresh_payment(payment_id: int, *, block: int | None = None, tx_hash: str | None = None) -> Payment:
    rec, kind, amount, rhash, payer, by, at, trf = client.contract("FeeLedger").functions.getPayment(
        payment_id).call()
    defaults = {"record_id": int(rec), "kind": int(kind), "amount_pesewas": int(amount), "receipt_hash": hex0x(rhash),
                "payer_address": payer.lower(), "payer_public_id": public_id(payer), "recorded_by": by.lower(),
                "at": ts_to_dt(at), "transfer_id": int(trf) or None}
    if block is not None:
        defaults.update(block_number=block, tx_hash=tx_hash or "")
    p, _ = Payment.objects.update_or_create(payment_id=payment_id, defaults=defaults)
    # A fresh chain restarts payment ids: a receipt from the old chain lets go of this id.
    PaymentReceipt.objects.filter(payment_id=payment_id).exclude(receipt_hash=p.receipt_hash).update(payment_id=None)
    if not PaymentReceipt.objects.filter(payment_id=payment_id).exists():
        rc = PaymentReceipt.objects.filter(receipt_hash=p.receipt_hash, payment_id__isnull=True).order_by("-created_at").first()
        if rc:
            rc.payment_id = payment_id
            rc.save(update_fields=["payment_id"])
    return p


# ---------------------------------------------------------------- side effects
def history(ctx: EventCtx, record_id: int, type_: str, text: str):
    parcel = Parcel.objects.filter(record_id=record_id).first()
    HistoryEvent.objects.update_or_create(tx_hash=ctx.tx_hash, log_index=ctx.log_index, defaults={
        "record_id": record_id, "parcel_id": parcel.parcel_id if parcel else f"#{record_id}", "type": type_,
        "text": text, "at": ctx.at, "block_number": ctx.block})


def note(ctx: EventCtx, *, kind: str, text: str, to_public_id: str | None = None, role: str | None = None,
         parcel_id: str | None = None, link: str | None = None, relay: bool = False):
    from landchain.notifications.service import notify
    notify(kind=kind, text=text, recipient_public_id=to_public_id, recipient_role=role, parcel_id=parcel_id,
           link=link or (f"/title/{parcel_id}" if parcel_id else None), at=ctx.at, source_event=ctx.chain_event,
           relay=relay, dedupe_key=f"{ctx.tx_hash}:{ctx.log_index}:{kind}:{to_public_id or role}")


def _pid(record_id: int) -> str:
    p = Parcel.objects.filter(record_id=record_id).only("parcel_id").first()
    return p.parcel_id if p else f"#{record_id}"


def _off_chain_reason(tx_hash: str) -> str | None:
    from landchain.chain.models import OfficerAction
    oa = OfficerAction.objects.filter(intent__tx_hash=tx_hash).exclude(reason__isnull=True).exclude(reason="").first()
    return oa.reason if oa else None


# ---------------------------------------------------------------- the mapping table
def handle(ctx: EventCtx, p: Pass):
    a, key = ctx.args, f"{ctx.contract}.{ctx.event}"
    idof = public_id

    def label(fn, args, records=()):
        p.labels.setdefault(ctx.tx_hash, (fn, args, list(records)))

    if key == "IdentityRegistry.ProfileSubmitted":
        refresh_identity(a["who"], submitted_at=ctx.at)
        label("submitProfile", f"{hex0x(a['cardHash'])[:10]}…, {'citizen' if a['citizen'] else 'non-citizen'}")
        note(ctx, kind="identity_submitted", role="id_officer", text=f"New identity request from {idof(a['who'])}",
             link="/review", relay=True)
    elif key == "IdentityRegistry.ProfileVerified":
        refresh_identity(a["who"])
        label("verifyProfile", idof(a["who"]))
        note(ctx, kind="identity_verified", to_public_id=idof(a["who"]), text="Your identity has been verified",
             link="/identity", relay=True)
    elif key == "IdentityRegistry.ProfileRejected":
        refresh_identity(a["who"])
        label("rejectProfile", idof(a["who"]))
        reason = _off_chain_reason(ctx.tx_hash)
        note(ctx, kind="identity_rejected", to_public_id=idof(a["who"]), link="/identity", relay=True,
             text="Your identity request was rejected" + (f": {reason}" if reason else ""))
    elif key in ("LandAccessControl.RoleGranted", "LandAccessControl.RoleRevoked"):
        refresh_roles()
        acl = client.contract("LandAccessControl")
        names = {hex0x(acl.functions[c]().call()): c for c in ROLE_NAMES}
        fn = "grantRole" if ctx.event == "RoleGranted" else "revokeRole"
        label(fn, f"{names.get(hex0x(a['role']), hex0x(a['role'])[:10])}, {a['account'].lower()[:10]}…")
    elif key == "TitleRegistry.ApplicationSubmitted":
        rec = int(a["recordId"])
        refresh_record(rec, ctx.block)
        refresh_application(int(a["appId"]))
        p.records.add(rec)
        label("submitApplication", f"\"{a['parcelId']}\", {int(a['pillars'])} pillars", [rec])
        history(ctx, rec, "Application", f"Applied by {idof(a['applicant'])}")
        note(ctx, kind="application_submitted", role="registrar", parcel_id=a["parcelId"], link="/review",
             text=f"New title application {a['parcelId']} waiting for your review")
        from landchain.documents.service import attach_for_record
        attach_for_record(rec, a["applicant"].lower())
    elif key == "TitleRegistry.ApplicationApproved":
        rec = int(a["recordId"])
        refresh_application(int(a["appId"]))
        refresh_record(rec, ctx.block)
        label("approveApplication", f"APP-{int(a['appId'])}", [rec])
    elif key == "TitleRegistry.ApplicationRejected":
        rec = int(a["recordId"])
        refresh_application(int(a["appId"]))
        refresh_record(rec, ctx.block)
        label("rejectApplication", f"APP-{int(a['appId'])}, \"{a['reason']}\"", [rec])
        history(ctx, rec, "Rejected", f"Rejected by the registrar: {a['reason']}")
        app = Application.objects.filter(app_id=int(a["appId"])).first()
        pid = _pid(rec)
        if app:
            note(ctx, kind="application_rejected", to_public_id=app.applicant_public_id, parcel_id=pid, relay=True,
                 text=f"Your application {pid} was rejected: {a['reason']}")
    elif key == "TitleRegistry.TitleMinted":
        rec = int(a["recordId"])
        refresh_record(rec, ctx.block)
        pid = _pid(rec)
        history(ctx, rec, "Registration", f"Title GLT #{int(a['tokenId'])} minted to {idof(a['owner'])}")
        note(ctx, kind="title_issued", to_public_id=idof(a["owner"]), parcel_id=pid, relay=True,
             text=f"Title GLT #{int(a['tokenId'])} issued for {pid}")
    elif key == "TitleRegistry.TransferRequested":
        rec = int(a["recordId"])
        refresh_transfer(int(a["transferId"]))
        refresh_record(rec, ctx.block)
        pid = _pid(rec)
        label("requestTransfer", f"\"{pid}\", {idof(a['to'])}", [rec])
        history(ctx, rec, "Transfer requested", f"{idof(a['from'])} asked to transfer to {idof(a['to'])}")
        note(ctx, kind="transfer_requested", role="registrar", parcel_id=pid, link="/review",
             text=f"Transfer of {pid} waiting for approval")
        note(ctx, kind="transfer_requested_to_you", to_public_id=idof(a["to"]), parcel_id=pid, relay=True,
             text=f"{idof(a['from'])} asked to transfer {pid} to you")
    elif key == "TitleRegistry.TransferApproved":
        rec = int(a["recordId"])
        refresh_transfer(int(a["transferId"]))
        refresh_record(rec, ctx.block)
        pid = _pid(rec)
        label("approveTransfer", f"TRF-{int(a['transferId'])}", [rec])
        history(ctx, rec, "Transfer", f"{idof(a['from'])} → {idof(a['to'])}, approved by the registrar")
        note(ctx, kind="transfer_received", to_public_id=idof(a["to"]), parcel_id=pid, relay=True,
             text=f"{pid} is now registered to you")
        note(ctx, kind="transfer_approved", to_public_id=idof(a["from"]), parcel_id=pid, relay=True,
             text=f"Transfer of {pid} approved")
    elif key == "TitleRegistry.TransferRejected":
        rec = int(a["recordId"])
        refresh_transfer(int(a["transferId"]))
        refresh_record(rec, ctx.block)
        pid = _pid(rec)
        label("rejectTransfer", f"TRF-{int(a['transferId'])}, \"{a['reason']}\"", [rec])
        history(ctx, rec, "Transfer rejected", f"Rejected by the registrar: {a['reason']}")
        t = TransferRequest.objects.filter(transfer_id=int(a["transferId"])).first()
        if t:
            note(ctx, kind="transfer_rejected", to_public_id=t.from_public_id, parcel_id=pid, relay=True,
                 text=f"Transfer of {pid} was rejected: {a['reason']}")
    elif key == "TitleRegistry.TransferCancelled":
        rec = int(a["recordId"])
        refresh_transfer(int(a["transferId"]))
        refresh_record(rec, ctx.block)
        label("cancelTransfer", f"TRF-{int(a['transferId'])}", [rec])
        history(ctx, rec, "Transfer cancelled", "Cancelled by the owner")
    elif key == "FeeLedger.PaymentRecorded":
        rec = int(a["recordId"])
        pay = refresh_payment(int(a["paymentId"]), block=ctx.block, tx_hash=ctx.tx_hash)
        pid = _pid(rec)
        kind = FEE_KINDS[int(a["kind"])]
        label("recordPayment", f"\"{pid}\", {kind}", [rec])
        note(ctx, kind="payment_recorded", to_public_id=pay.payer_public_id, parcel_id=pid,
             text=f"{kind} receipt of {cedi(int(a['amountPesewas']))} recorded for {pid}")
    # ERC-721 Transfer / Approval and RoleAdminChanged: covered by the refreshes above.


def intent_result(intent) -> dict | None:
    """intent.result after confirmation, from the events of its transaction."""
    from .models import ChainEvent
    evs = list(ChainEvent.objects.filter(tx_hash=intent.tx_hash).order_by("log_index"))
    out: dict = {}
    for e in evs:
        a = e.args
        if e.event == "ApplicationSubmitted":
            out.update(application_id=f"APP-{a['appId']}", record_id=int(a["recordId"]), parcel_id=a["parcelId"])
        elif e.event in ("ApplicationApproved", "ApplicationRejected"):
            out.update(application_id=f"APP-{a['appId']}", record_id=int(a["recordId"]),
                       parcel_id=_pid(int(a["recordId"])))
        elif e.event == "TitleMinted":
            out.update(title_no=int(a["tokenId"]), record_id=int(a["recordId"]), parcel_id=_pid(int(a["recordId"])))
        elif e.event in ("TransferRequested", "TransferApproved", "TransferRejected", "TransferCancelled"):
            out.update(transfer_id=f"TRF-{a['transferId']}", record_id=int(a["recordId"]),
                       parcel_id=_pid(int(a["recordId"])))
        elif e.event == "PaymentRecorded":
            out.update(payment_id=f"PAY-{a['paymentId']}", record_id=int(a["recordId"]),
                       parcel_id=_pid(int(a["recordId"])))
        elif e.event in ("ProfileSubmitted", "ProfileVerified", "ProfileRejected"):
            out.update(public_id=public_id(a["who"]))
    return out or None
