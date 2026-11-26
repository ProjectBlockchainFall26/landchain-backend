"""Parcel and map reads (task C5) and the boundary check (task C6). Spec 9.2 and 9.5."""
from __future__ import annotations

import re

from django.contrib.gis.geos import Polygon
from django.db.models import Count, Prefetch, Q
from rest_framework.response import Response
from rest_framework.views import APIView

from landchain.chain.encoding import INTEREST, PARCEL_STATUS, acres_str
from landchain.core.errors import NotFound, Validation
from landchain.core.pagination import csv_param, paginate
from landchain.core.permissions import IsSignedIn, Public, viewer

from . import geo
from .models import OwnerHistory, Parcel, TransferRequest
from .selectors import current_parcel, normalize_parcel_id
from .serializers import ctx_for, history_obj, parcel_detail, parcel_list_item

ORDERING = {"parcel_id": "parcel_id", "-registered_at": "-registered_at", "-updated_at": "-updated_at",
            "acres": "acres_x100", "-acres": "-acres_x100"}


def base_qs():
    return Parcel.objects.filter(is_current=True).prefetch_related(
        Prefetch("owners", queryset=OwnerHistory.objects.order_by("position")))


def _statuses(request, default="pending,registered,transfer_pending") -> list[int]:
    names = csv_param(request, "status", default)
    bad = [n for n in names if n not in PARCEL_STATUS]
    if bad:
        raise Validation(f"Unknown status {bad[0]}", field_errors={"status": [f"Use {', '.join(PARCEL_STATUS)}"]})
    return [PARCEL_STATUS.index(n) for n in names]


def _geojson_feature(p: Parcel, ctx) -> dict:
    ring = [[round(b / 1e6, 6), round(a / 1e6, 6)] for a, b in zip(p.lats_micro, p.lngs_micro, strict=False)]
    if ring:
        ring.append(ring[0])
    return {"type": "Feature", "id": p.parcel_id,
            "geometry": {"type": "Polygon", "coordinates": [ring]},
            "properties": {"parcel_id": p.parcel_id, "status": p.status_name, "title_no": p.token_id or None,
                           "acres": acres_str(p.acres_x100), "interest": p.interest_name, "holder": p.holder,
                           "region": p.region, "owner": ctx.ref(p.owner_public_id)}}


class ParcelsView(APIView):
    """GET /api/v1/parcels [Public]."""

    permission_classes = [Public]

    def get(self, request, *args, **kwargs):
        q = request.query_params
        qs = base_qs().filter(status__in=_statuses(request))
        if q.get("bbox"):
            try:
                min_lng, min_lat, max_lng, max_lat = (float(x) for x in q["bbox"].split(","))
            except ValueError:
                raise Validation("bbox is minLng,minLat,maxLng,maxLat",
                                 field_errors={"bbox": ["Use minLng,minLat,maxLng,maxLat"]}) from None
            qs = qs.filter(boundary__bboverlaps=Polygon.from_bbox((min_lng, min_lat, max_lng, max_lat)))
        if q.get("owner"):
            qs = qs.filter(owner_public_id=q["owner"].strip())
        if q.get("region"):
            qs = qs.filter(region__iexact=q["region"].strip())
        if q.get("interest"):
            try:
                qs = qs.filter(interest=[i.lower() for i in INTEREST].index(q["interest"].strip().lower()))
            except ValueError:
                raise Validation("Unknown interest", field_errors={"interest": [f"Use {', '.join(INTEREST)}"]}) \
                    from None
        order = ORDERING.get(q.get("ordering", "parcel_id"))
        if order is None:
            raise Validation("Unknown ordering", field_errors={"ordering": [f"Use {', '.join(ORDERING)}"]})
        qs = qs.order_by(order, "record_id")
        ctx = ctx_for(request)
        ctx.people.prefetch(list(qs.values_list("owner_public_id", flat=True)))
        if q.get("format") == "geojson":
            return Response({"type": "FeatureCollection", "features": [_geojson_feature(p, ctx) for p in qs]})
        return paginate(request, qs, lambda p: parcel_list_item(p, ctx), view=self)


class ParcelsSearchView(APIView):
    """GET /api/v1/parcels/search [Public]: parcel ID, owner ID or token #. Exact match first, then contains."""

    permission_classes = [Public]

    def get(self, request, *args, **kwargs):
        raw = (request.query_params.get("q") or "").strip()
        ctx = ctx_for(request)
        if not raw:
            return Response({"results": [], "best": None})
        qs = base_qs().exclude(status=3)
        exact, contains = [], []
        m = re.fullmatch(r"(?:#|glt\s*#?)\s*(\d+)", raw, flags=re.I)
        if m or raw.isdigit():
            n = int(m.group(1) if m else raw)
            exact = list(qs.filter(token_id=n))
        if raw.upper().startswith("GH-"):
            pid = "GH-" + raw[3:].lower()
            exact += [p for p in qs.filter(owner_public_id=pid) if p not in exact]
            contains = list(qs.filter(owner_public_id__startswith=pid).exclude(owner_public_id=pid))
        else:
            up = raw.upper()
            exact += [p for p in qs.filter(parcel_id=up) if p not in exact]
            contains = list(qs.filter(Q(parcel_id__icontains=up) | Q(holder__icontains=raw) |
                                      Q(plan_number__icontains=raw)).exclude(parcel_id=up)[:50])
        results = exact + [p for p in contains if p not in exact]
        return Response({"results": [parcel_list_item(p, ctx) for p in results[:50]],
                         "best": results[0].parcel_id if results else None})


class ParcelsDetailView(APIView):
    """GET /api/v1/parcels/{parcel_id} [Public, privacy-filtered]."""

    permission_classes = [Public]

    def get(self, request, parcel_id, *args, **kwargs):
        rid = request.query_params.get("record_id")
        p = current_parcel(parcel_id, record_id=int(rid) if rid and rid.isdigit() else None)
        return Response(parcel_detail(p, ctx_for(request)))


class ParcelsDetailHistoryView(APIView):
    """GET /api/v1/parcels/{parcel_id}/history [Public]. Oldest first, current record only (or ?record_id=)."""

    permission_classes = [Public]

    def get(self, request, parcel_id, *args, **kwargs):
        from .models import HistoryEvent
        rid = request.query_params.get("record_id")
        p = current_parcel(parcel_id, record_id=int(rid) if rid and rid.isdigit() else None)
        rows = HistoryEvent.objects.filter(record_id=p.record_id).order_by("block_number", "log_index")
        return Response({"parcel_id": p.parcel_id, "results": [history_obj(h) for h in rows]})


class ParcelsNextIdView(APIView):
    """GET /api/v1/parcels/next-id?prefix=GA-BRK [Public]."""

    permission_classes = [Public]

    def get(self, request, *args, **kwargs):
        prefix = (request.query_params.get("prefix") or "GA-BRK").strip().upper().rstrip("-")
        if not re.fullmatch(r"[A-Z]{2}-[A-Z]{3}", prefix):
            raise Validation("prefix looks like GA-BRK", field_errors={"prefix": ["Use two letters, dash, three"]})
        used = {int(x[-4:]) for x in Parcel.objects.filter(parcel_id__startswith=prefix + "-")
                .exclude(status=3, is_current=True).values_list("parcel_id", flat=True)}
        n = (max(used) + 1) if used else 1
        while n in used:
            n += 1
        if n > 9999:
            raise NotFound(f"No free parcel IDs left under {prefix}.")
        return Response({"parcel_id": f"{prefix}-{n:04d}"})


def parse_pillars(raw, field: str = "pillars") -> list[list[float]]:
    try:
        pts = [[float(p[0]), float(p[1])] for p in (raw or [])]
        if any(len(p) != 2 for p in (raw or [])):
            raise ValueError
    except (TypeError, ValueError, IndexError):
        raise Validation("pillars is a list of [lat, lng] pairs",
                         field_errors={field: ["Use a list of [lat, lng] pairs"]}) from None
    return pts


class ParcelsBoundaryCheckView(APIView):
    """POST /api/v1/parcels/boundary-check [Public]."""

    permission_classes = [Public]

    def post(self, request, *args, **kwargs):
        pillars = parse_pillars(request.data.get("pillars"))
        ignore = request.data.get("ignore_parcel_id")
        return Response(geo.check_boundary(pillars, normalize_parcel_id(ignore) if ignore else None))


class StatsView(APIView):
    """GET /api/v1/stats [Public]: the "Register snapshot" card."""

    permission_classes = [Public]

    def get(self, request, *args, **kwargs):
        from landchain.core.middleware import indexed_block
        cur = Parcel.objects.filter(is_current=True)
        by = dict(cur.values_list("status").annotate(n=Count("record_id")))
        by_status = {name: by.get(i, 0) for i, name in enumerate(PARCEL_STATUS)}
        titled = cur.filter(status__in=[1, 2])
        return Response({
            "registered_titles": titled.count(),
            "applications_pending": by_status["pending"],
            "completed_transfers": TransferRequest.objects.filter(decision=1, parcel__is_current=True).count(),
            "title_holders": titled.values("owner_public_id").distinct().count(),
            "by_status": {"registered": by_status["registered"], "transfer_pending": by_status["transfer_pending"],
                          "pending": by_status["pending"], "rejected": by_status["rejected"]},
            "block": indexed_block(),
        })


class MeParcelsView(APIView):
    """GET /api/v1/me/parcels [IsSignedIn]: owned, applications (pending|rejected) and optionally past."""

    permission_classes = [IsSignedIn]

    def get(self, request, *args, **kwargs):
        p = viewer(request)
        include = set(csv_param(request, "include", "owned,applications"))
        ctx = ctx_for(request)
        out = {"owned": [], "applications": [], "past": []}
        owned = []
        if p.public_id:
            owned = list(base_qs().filter(owner_public_id=p.public_id, status__in=[1, 2]).order_by("parcel_id"))
            if "owned" in include:
                out["owned"] = [parcel_list_item(x, ctx) for x in owned]
            if "applications" in include:
                out["applications"] = [parcel_list_item(x, ctx) for x in base_qs().filter(
                    applicant_public_id=p.public_id, status__in=[0, 3]).order_by("-record_id")]
            if "past" in include:
                out["past"] = [parcel_list_item(x, ctx) for x in base_qs().filter(
                    owners__public_id=p.public_id).exclude(owner_public_id=p.public_id).distinct()]
        out["totals"] = {"count": len(owned), "acres": acres_str(sum(x.acres_x100 for x in owned))}
        return Response(out)
