"""Applications: submit, list, review, approve, reject (task D5, spec 9.6)."""
from __future__ import annotations

from rest_framework.response import Response
from rest_framework.views import APIView

from landchain.chain import service
from landchain.chain.encoding import GPS_RE, INTEREST, PARCEL_ID_RE, acres_str, interest_index, to_micro
from landchain.chain.views import intent_response
from landchain.core.errors import NotFound, Validation
from landchain.core.idempotency import idempotent
from landchain.core.ids import parse_id
from landchain.core.pagination import paginate
from landchain.core.permissions import IsRegistrar, IsSignedIn, IsVerifiedCitizen, viewer
from landchain.core.ratelimit import limit
from landchain.documents.models import REQUIRED_DOC_TYPES, Document
from landchain.fees.models import Payment
from landchain.fees.schedule import FEE_INFO, estimate
from landchain.fees.serializers import payment_obj

from . import geo
from .models import Application
from .serializers import Ctx, application_obj, ctx_for, parcel_detail, parcel_list_item
from .views_parcels import parse_pillars

DECISIONS = ["waiting", "approved", "rejected", "cancelled"]


def validate_application(data, profile) -> tuple[dict, list[Document], list[list[float]]]:
    fe: dict[str, list[str]] = {}
    pid = str(data.get("parcel_id") or "").strip().upper()
    if not PARCEL_ID_RE.fullmatch(pid):
        fe["parcel_id"] = ["Parcel ID must look like GA-BRK-0015"]
    interest = str(data.get("interest") or "")
    try:
        interest_i = interest_index(interest)
    except ValueError:
        interest_i = 0
        fe["interest"] = [f"Use one of: {', '.join(INTEREST)}"]
    holder = str(data.get("holder") or "").strip()
    if not holder:
        fe["holder"] = ["Name the allodial holder"]
    region = str(data.get("region") or "").strip()
    if not region:
        fe["region"] = ["Pick the region"]
    location = str(data.get("location") or "").strip() or f"Berekuso, {region} Region"
    plan = str(data.get("plan_number") or "").strip().upper()
    if not plan:
        fe["plan_number"] = ["Add the regional plan number from the site plan"]
    gps = str(data.get("gps_address") or "").strip().upper()
    if gps and not GPS_RE.fullmatch(gps):
        fe["gps_address"] = ["Format: two letters, then numbers, e.g. EA-1805-5795"]
    pillars = parse_pillars(data.get("pillars"))
    check = geo.check_boundary(pillars)
    if check["error"] and not check["duplicate_boundary"]:  # duplicates are refused by the contract (422)
        fe["pillars"] = [check["error"]]
    ids = data.get("documents") or []
    docs = list(Document.objects.filter(id__in=[str(x) for x in ids], uploaded_by=profile))
    if len(docs) != len(set(ids)):
        fe["documents"] = ["Upload each document first. Some of these aren't yours or don't exist."]
    elif any(d.status == Document.Status.ATTACHED and d.parcel_record_id for d in docs):
        fe["documents"] = ["One of these documents is already attached to another record."]
    else:
        have = {d.doc_type for d in docs}
        missing = [t for t in REQUIRED_DOC_TYPES if t not in have]
        if missing:
            fe["documents"] = [f"Still needed: {', '.join(missing)}."]
    if fe:
        raise Validation(next(iter(fe.values()))[0], field_errors=fe)
    order = {t: i for i, t in enumerate(["Site plan", "Indenture", "Search report", "Consent / concurrence"])}
    docs.sort(key=lambda d: order.get(d.doc_type, 9))
    fields = {"parcelId": pid, "interest": interest_i, "holder": holder, "region": region, "location": location,
              "planNumber": plan, "gpsAddress": gps, "acresX100": check["acres_x100"],
              "lats": [to_micro(a) for a, _ in pillars], "lngs": [to_micro(b) for _, b in pillars],
              "docs": [(d.doc_type, d.sha256) for d in docs]}
    return fields, docs, pillars


def _application(id_) -> Application:
    app = Application.objects.select_related("parcel").filter(app_id=parse_id(id_, "APP", what="Application")).first()
    if app is None:
        raise NotFound("Application not found")
    return app


class ApplicationsView(APIView):
    """POST /api/v1/applications [IsVerifiedCitizen] and GET /api/v1/applications [IsSignedIn]."""

    def get_permissions(self):
        return [IsVerifiedCitizen()] if self.request.method == "POST" else [IsSignedIn()]

    @idempotent
    def post(self, request, *args, **kwargs):
        limit(request, "prepare")
        p = viewer(request)
        f, docs, pillars = validate_application(request.data, p)
        args = [(f["parcelId"], f["interest"], f["holder"], f["region"], f["location"], f["planNumber"],
                 f["gpsAddress"], f["acresX100"], f["lats"], f["lngs"], f["docs"])]
        intent = service.prepare(
            profile=p, contract="TitleRegistry", function="submitApplication", args=args,
            label=f"\"{f['parcelId']}\", {len(pillars)} pillars", success="Application submitted",
            idempotency_key=request.headers.get("Idempotency-Key"))
        return intent_response(request, intent, created=True, extra={"preview": {
            "parcel_id": f["parcelId"], "acres": acres_str(f["acresX100"]), "acres_x100": f["acresX100"],
            "docs": [{"doc_type": t, "sha256": h} for t, h in f["docs"]]}})

    def get(self, request, *args, **kwargs):
        me, q = viewer(request), request.query_params
        qs = Application.objects.select_related("parcel").order_by("-app_id")
        if me.is_officer:
            dec = q.get("decision", "waiting")
        else:
            qs = qs.filter(applicant_public_id=me.public_id or "-")
            dec = q.get("decision")
        if dec:
            names = [x.strip() for x in dec.split(",")]
            if any(n not in DECISIONS for n in names):
                raise Validation("Unknown decision", field_errors={"decision": ["Use waiting, approved or rejected"]})
            qs = qs.filter(decision__in=[DECISIONS.index(n) for n in names])
        if q.get("parcel_id"):
            qs = qs.filter(parcel__parcel_id=q["parcel_id"].strip().upper())
        if q.get("applicant"):
            qs = qs.filter(applicant_public_id=q["applicant"].strip())
        ctx = ctx_for(request)
        return paginate(request, qs, lambda a: {**application_obj(a, ctx), "parcel": parcel_list_item(a.parcel, ctx)},
                        view=self)


def fee_checklist(parcel, ctx: Ctx, kinds=("Official search", "Stamp duty", "First registration"),
                  transfer_id: int | None = None) -> list[dict]:
    rows = []
    pays = list(Payment.objects.filter(record_id=parcel.record_id))
    acres = parcel.acres_x100 / 100
    for kind in kinds:
        if kind == "Transfer":
            pay = next((x for x in pays if x.kind == 3 and x.transfer_id == transfer_id), None)
        else:
            pay = next((x for x in pays if x.kind_name == kind), None)
        rows.append({"kind": kind, "required": kind != "Official search", "recorded": pay is not None,
                     "payment": payment_obj(pay, ctx.viewer, ctx.people, parcel.parcel_id) if pay else None,
                     "suggested_ghs": estimate(kind, acres)["suggested_ghs"], "how": FEE_INFO[kind]["how"],
                     "paid_to": FEE_INFO[kind]["paid_to"]})
    return rows


class ApplicationsDetailView(APIView):
    """GET /api/v1/applications/{id} [IsOfficer or applicant]: the review dialog."""

    permission_classes = [IsSignedIn]

    def get(self, request, id, *args, **kwargs):
        app = _application(id)
        me = viewer(request)
        if not me.is_officer and me.public_id != app.applicant_public_id:
            raise NotFound("Application not found")
        ctx = ctx_for(request)
        obj = application_obj(app, ctx)
        can = app.decision == 0 and obj["fees_ready"] and me.is_registrar
        blocked = None
        if app.decision != 0:
            blocked = "This application has already been decided"
        elif obj["missing_fees"]:
            blocked = ("Record the stamp duty and registration fee receipts first. The contract refuses approval "
                       "without them." if len(obj["missing_fees"]) == 2 else
                       f"Record the {obj['missing_fees'][0].lower()} receipt first. The contract refuses approval "
                       "without it.")
        elif not me.is_registrar:
            blocked = "Only the registrar can approve a registration"
        return Response({"application": obj, "parcel": parcel_detail(app.parcel, ctx),
                         "fee_checklist": fee_checklist(app.parcel, ctx), "can_approve": bool(can),
                         "blocked_reason": blocked})


class ApplicationsDetailApproveView(APIView):
    """POST /api/v1/applications/{id}/approve [IsRegistrar]: mints the title NFT."""

    permission_classes = [IsRegistrar]
    forbidden_message = "Only the registrar can approve a registration"

    @idempotent
    def post(self, request, id, *args, **kwargs):
        app = _application(id)
        intent = service.write(
            signer="registrar", contract="TitleRegistry", function="approveApplication", args=[app.app_id],
            label=f"APP-{app.app_id}", success="Registered: title NFT minted", by=viewer(request),
            target=f"APP-{app.app_id}", note=request.data.get("note"), request=request,
            idempotency_key=request.headers.get("Idempotency-Key"))

        def then():
            app.parcel.refresh_from_db()
            return {"parcel": parcel_detail(app.parcel, ctx_for(request))}
        return intent_response(request, intent, then=then)


class ApplicationsDetailRejectView(APIView):
    """POST /api/v1/applications/{id}/reject [IsRegistrar]. The reason is public on chain."""

    permission_classes = [IsRegistrar]
    forbidden_message = "Only the registrar can reject a registration"

    @idempotent
    def post(self, request, id, *args, **kwargs):
        reason = str(request.data.get("reason") or "").strip()
        if not reason or len(reason) > 280:
            raise Validation("A reason is required to reject",
                             field_errors={"reason": ["A reason (1 to 280 characters) is required to reject"]})
        app = _application(id)
        intent = service.write(
            signer="registrar", contract="TitleRegistry", function="rejectApplication", args=[app.app_id, reason],
            label=f"APP-{app.app_id}, \"{reason}\"", success="Application rejected", by=viewer(request),
            target=f"APP-{app.app_id}", note=reason, request=request,
            idempotency_key=request.headers.get("Idempotency-Key"))

        def then():
            app.parcel.refresh_from_db()
            return {"parcel": parcel_detail(app.parcel, ctx_for(request))}
        return intent_response(request, intent, then=then)
