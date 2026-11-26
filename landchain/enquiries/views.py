"""Enquiries: send, owner inbox, mark read / answered (task A8, spec 9.11)."""
from __future__ import annotations

import hashlib

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from landchain.chain.encoding import iso
from landchain.core import privacy
from landchain.core.errors import ApiError, Conflict, NotFound, Validation
from landchain.core.pagination import paginate
from landchain.core.permissions import IsSignedIn, Public, viewer
from landchain.core.ratelimit import client_ip, limit
from landchain.registry.selectors import current_parcel

from .models import Enquiry


def enquiry_obj(e: Enquiry) -> dict:
    return {"id": e.id, "parcel_id": e.parcel_id, "from_public_id": e.from_public_id, "name": e.name,
            "contact": e.contact, "message": e.message, "status": e.status, "at": iso(e.created_at)}


def _check_captcha(token: str, ip: str):
    if not settings.CAPTCHA_SECRET:
        return
    import requests
    ok = False
    if token:
        try:
            r = requests.post(settings.CAPTCHA_VERIFY_URL, timeout=10,
                              data={"secret": settings.CAPTCHA_SECRET, "response": token, "remoteip": ip})
            ok = bool(r.json().get("success"))
        except Exception:
            ok = False
    if not ok:
        raise Validation("Complete the check that you're not a robot.",
                         field_errors={"captcha_token": ["Complete the captcha"]})


class ParcelsDetailEnquiriesView(APIView):
    """POST /api/v1/parcels/{parcel_id}/enquiries [Public]. Goes to the owner without revealing them."""

    permission_classes = [Public]

    def post(self, request, parcel_id, *args, **kwargs):
        me = viewer(request)
        d = request.data
        name, contact, message = (str(d.get(k) or "").strip() for k in ("name", "contact", "message"))
        fe = {}
        if not 2 <= len(name) <= 120:
            fe["name"] = ["Your name, 2 to 120 characters"]
        if not 5 <= len(contact) <= 160:
            fe["contact"] = ["A phone number or email, 5 to 160 characters"]
        if not 1 <= len(message) <= 2000:
            fe["message"] = ["A message of up to 2000 characters"]
        if fe:
            raise Validation(next(iter(fe.values()))[0], field_errors=fe)
        p = current_parcel(parcel_id)
        if me is not None and me.is_officer:
            raise ApiError("Lands Commission accounts can't send enquiries.", code="CANNOT_ENQUIRE", status_code=403)
        if me is not None and me.public_id and me.public_id == p.owner_public_id:
            raise ApiError("You own this parcel.", code="CANNOT_ENQUIRE", status_code=403)
        if p.status == 3:
            raise Conflict("This application was rejected, so there is no owner to contact.")
        if p.status == 0:
            raise Conflict("This parcel isn't registered yet, so there is no owner to contact.")
        ip = client_ip(request)
        if me is None:
            _check_captcha(str(d.get("captcha_token") or ""), ip)
        limit(request, "enquiry")
        from landchain.accounts.models import Profile
        owner = Profile.objects.filter(public_id=p.owner_public_id).first()
        e = Enquiry.objects.create(
            parcel_id=p.parcel_id, record_id=p.record_id, to_public_id=p.owner_public_id, to_profile=owner,
            from_profile=me, from_public_id=(me.public_id if me and me.public_id else "public"), name=name,
            contact=contact, message=message,
            ip_hash=hashlib.sha256((ip + settings.ENQUIRY_IP_SALT).encode()).hexdigest())
        from landchain.notifications.service import notify
        notify(kind="enquiry_received", recipient_public_id=p.owner_public_id, recipient_profile=owner,
               parcel_id=p.parcel_id, link=f"/title/{p.parcel_id}", relay=True,
               text=f"New enquiry about {p.parcel_id} from {name}. Open the title to read it.",
               relay_extra=f"Message: {message}\nContact: {name}, {contact}", dedupe_key=f"enquiry:{e.id}")
        Enquiry.objects.filter(pk=e.pk).update(relayed_at=timezone.now())
        return Response({"id": e.id, "parcel_id": p.parcel_id, "status": "sent",
                         "message": "Enquiry sent to the owner. If they're interested, they'll contact you."},
                        status=201)


class MeEnquiriesView(APIView):
    """GET /api/v1/me/enquiries [IsSignedIn]: only enquiries addressed to my public ID."""

    permission_classes = [IsSignedIn]

    def get(self, request, *args, **kwargs):
        me = viewer(request)
        qs = Enquiry.objects.filter(to_public_id=me.public_id or "-")
        if request.query_params.get("parcel_id"):
            qs = qs.filter(parcel_id=request.query_params["parcel_id"].strip().upper())
        if request.query_params.get("status"):
            qs = qs.filter(status__in=request.query_params["status"].split(","))
        new = Enquiry.objects.filter(to_public_id=me.public_id or "-", status="new").count()
        return paginate(request, qs.order_by("-created_at"), enquiry_obj, view=self, extra={"new": new})


class EnquiriesDetailView(APIView):
    """PATCH /api/v1/enquiries/{id} [recipient]: {"status": "read" | "answered"}."""

    permission_classes = [IsSignedIn]

    def patch(self, request, id, *args, **kwargs):
        e = get_object_or_404(Enquiry, pk=id)
        if not privacy.can_read_enquiry(viewer(request), e):
            raise NotFound("Enquiry not found.")
        status = str(request.data.get("status") or "")
        if status not in ("read", "answered"):
            raise Validation("Use read or answered", field_errors={"status": ["Use read or answered"]})
        now = timezone.now()
        if status == "read" and e.status == "new":
            e.status, e.read_at = "read", now
        elif status == "answered":
            e.status, e.answered_at = "answered", now
            e.read_at = e.read_at or now
        e.save(update_fields=["status", "read_at", "answered_at"])
        return Response(enquiry_obj(e))
