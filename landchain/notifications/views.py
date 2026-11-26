"""Notification inbox (task A7, spec 9.2)."""
from rest_framework.response import Response
from rest_framework.views import APIView

from landchain.chain.encoding import iso
from landchain.core.errors import Validation
from landchain.core.pagination import before_filter, paginate
from landchain.core.permissions import IsSignedIn, viewer

from .models import NotificationRead
from .service import for_profile, mark_read, unread_for


def notification_obj(n, read: bool) -> dict:
    return {"id": n.id, "kind": n.kind, "text": n.text, "parcel_id": n.parcel_id, "link": n.link,
            "audience": n.audience, "at": iso(n.at), "read": read}


class MeNotificationsView(APIView):
    """GET /api/v1/me/notifications [IsSignedIn]: to me, to my roles, and new enquiries about my parcels."""

    permission_classes = [IsSignedIn]

    def get(self, request, *args, **kwargs):
        me = viewer(request)
        qs = for_profile(me)
        if request.query_params.get("unread") in ("1", "true"):
            qs = qs.exclude(reads__profile=me)
        qs = before_filter(request, qs, "at").order_by("-at", "-id")
        read_ids = set(NotificationRead.objects.filter(profile=me).values_list("notification_id", flat=True))
        return paginate(request, qs, lambda n: notification_obj(n, n.id in read_ids), view=self,
                        extra={"unread": unread_for(me).count()})


class MeNotificationsReadView(APIView):
    """POST /api/v1/me/notifications/read [IsSignedIn]: {"ids": [...]} or {"all": true}."""

    permission_classes = [IsSignedIn]

    def post(self, request, *args, **kwargs):
        me = viewer(request)
        ids, all_ = request.data.get("ids"), bool(request.data.get("all"))
        if not all_ and not isinstance(ids, list):
            raise Validation("Send ids or all", field_errors={"ids": ["A list of notification ids, or all: true"]})
        mark_read(me, ids=[str(i) for i in (ids or [])], all_=all_)
        return Response({"unread": unread_for(me).count()})
