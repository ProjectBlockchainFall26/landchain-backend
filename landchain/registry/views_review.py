"""Review queue and nav badge counts (task D7, spec 9.10)."""
from __future__ import annotations

from rest_framework.response import Response
from rest_framework.views import APIView

from landchain.chain.encoding import acres_str, iso
from landchain.core.permissions import IsOfficer, viewer

from .models import Application, ChainIdentity, TransferRequest
from .serializers import Ctx, missing_registration_fees, transfer_fee_recorded


def pending_identities():
    return ChainIdentity.objects.filter(status=1).order_by("submitted_at", "address")


def waiting_applications():
    return Application.objects.filter(decision=0, parcel__is_current=True).select_related("parcel").order_by("app_id")


def waiting_transfers():
    return TransferRequest.objects.filter(decision=0).select_related("parcel").order_by("transfer_id")


def counts_for(profile) -> dict:
    ids, apps, trfs = pending_identities().count(), waiting_applications().count(), waiting_transfers().count()
    actionable = 0
    if profile is not None and profile.is_id_officer:
        actionable += ids
    if profile is not None and profile.is_registrar:
        actionable += apps + trfs
    return {"total": ids + apps + trfs, "actionable": actionable, "identities": ids, "applications": apps,
            "transfers": trfs}


class ReviewQueueView(APIView):
    """GET /api/v1/review/queue [IsOfficer]."""

    permission_classes = [IsOfficer]

    def get(self, request, *args, **kwargs):
        from landchain.accounts.models import Profile
        me = viewer(request)
        ctx = Ctx(me)
        ids = list(pending_identities())
        names = {p.wallet_address: p.full_name for p in Profile.objects.filter(
            wallet_address__in=[i.address for i in ids])}
        apps = list(waiting_applications())
        trfs = list(waiting_transfers())
        return Response({
            "acting_as": {"name": me.full_name, "roles": me.role_labels},
            "identities": {"count": len(ids), "can_act": me.is_id_officer, "items": [
                {"public_id": i.public_id, "name": names.get(i.address) or None,
                 "citizenship": "citizen" if i.citizen else "non-citizen", "submitted_at": iso(i.submitted_at)}
                for i in ids]},
            "applications": {"count": len(apps), "can_act": me.is_registrar, "items": [
                {"id": f"APP-{a.app_id}", "parcel_id": a.parcel.parcel_id, "holder": a.parcel.holder,
                 "applicant": ctx.ref(a.applicant_public_id), "acres": acres_str(a.parcel.acres_x100),
                 "created_at": iso(a.created_at), "fees_ready": not missing_registration_fees(a.parcel.record_id)}
                for a in apps]},
            "transfers": {"count": len(trfs), "can_act": me.is_registrar, "items": [
                {"id": f"TRF-{t.transfer_id}", "parcel_id": t.parcel.parcel_id, "from": ctx.ref(t.from_public_id),
                 "to": ctx.ref(t.to_public_id), "requested_at": iso(t.requested_at),
                 "transfer_fee_recorded": transfer_fee_recorded(t)} for t in trfs]},
        })


class ReviewCountsView(APIView):
    """GET /api/v1/review/counts [IsOfficer]."""

    permission_classes = [IsOfficer]

    def get(self, request, *args, **kwargs):
        return Response(counts_for(viewer(request)))
