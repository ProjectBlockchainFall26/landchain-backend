"""Activity log GET /activity (task C7, spec 9.12): every contract call, newest first, with refusals."""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from django.conf import settings
from django.utils.dateparse import parse_datetime
from rest_framework.response import Response
from rest_framework.views import APIView

from landchain.chain.encoding import iso
from landchain.chain.models import RevertLog
from landchain.core import privacy
from landchain.core.errors import Validation
from landchain.core.permissions import Public, viewer

from .models import ChainTx

CONTRACTS = ["IdentityRegistry", "TitleRegistry", "FeeLedger", "LandAccessControl"]


def _eth(wei) -> str:
    return f"{Decimal(wei) / Decimal(10**18):.6f}"


def tx_row(t: ChainTx, v, people) -> dict:
    return {"tx_hash": t.tx_hash, "contract": t.contract, "function": t.function, "args_label": t.args_label,
            "call": f"{t.contract}.{t.function}({t.args_label})", "from": privacy.person_ref(v, t.from_public_id, people),
            "block": t.block_number, "at": iso(t.at), "status": t.status, "error": None, "gas_used": t.gas_used,
            "cost_eth": _eth(t.cost_wei)}


def revert_row(r: RevertLog, v, people) -> dict:
    return {"tx_hash": r.intent.tx_hash if r.intent_id and r.intent.tx_hash else None, "contract": r.contract,
            "function": r.function, "args_label": r.args_label, "call": f"{r.contract}.{r.function}({r.args_label})",
            "from": privacy.person_ref(v, r.from_public_id, people) if r.from_public_id else None,
            "block": r.intent.block_number if r.intent_id else None, "at": iso(r.created_at), "status": "Reverted",
            "error": r.error, "gas_used": None, "cost_eth": None}


class ActivityView(APIView):
    """GET /api/v1/activity [Public, names filtered]. ?parcel=&from=&contract=&status=&before=&page_size="""

    permission_classes = [Public]

    def get(self, request, *args, **kwargs):
        q = request.query_params
        v = viewer(request)
        people = privacy.PeopleIndex()
        txs = ChainTx.objects.filter(chain_id=settings.CHAIN_ID)
        revs = RevertLog.objects.filter(chain_id=settings.CHAIN_ID).select_related("intent")
        if q.get("parcel"):
            txs, revs = txs.filter(args_label__icontains=q["parcel"]), revs.filter(args_label__icontains=q["parcel"])
        if q.get("from"):
            pid = "GH-" + q["from"].strip()[3:].lower()
            txs, revs = txs.filter(from_public_id=pid), revs.filter(from_public_id=pid)
        if q.get("contract"):
            names = [c.strip() for c in q["contract"].split(",")]
            if any(c not in CONTRACTS for c in names):
                raise Validation("Unknown contract", field_errors={"contract": [f"Use {', '.join(CONTRACTS)}"]})
            txs, revs = txs.filter(contract__in=names), revs.filter(contract__in=names)
        status = q.get("status")
        if status == "Success":
            revs = revs.none()
        elif status == "Reverted":
            txs = txs.filter(status="Reverted")
        elif status:
            raise Validation("Use Success or Reverted", field_errors={"status": ["Use Success or Reverted"]})
        if q.get("before"):
            dt = parse_datetime(q["before"].replace(" ", "+"))
            if dt is None:
                raise Validation("before must be an ISO 8601 time", field_errors={"before": ["Use ISO 8601"]})
            txs, revs = txs.filter(at__lt=dt), revs.filter(created_at__lt=dt)
        try:
            size = min(int(q.get("page_size", 50)), 200)
            page = max(int(q.get("page", 1)), 1)
        except ValueError:
            raise Validation("page and page_size are numbers") from None
        need = page * size
        merged = [("t", t.at, t) for t in txs.order_by("-at", "-block_number", "-tx_index")[:need]] + \
                 [("r", r.created_at, r) for r in revs.order_by("-created_at")[:need]]
        floor = datetime(1970, 1, 1, tzinfo=UTC)
        merged.sort(key=lambda x: x[1] or floor, reverse=True)
        chunk = merged[(page - 1) * size: page * size]
        ids = [x[2].from_public_id for x in chunk if x[2].from_public_id]
        people.prefetch(ids)
        results = [tx_row(o, v, people) if k == "t" else revert_row(o, v, people) for k, _, o in chunk]
        count = txs.count() + revs.count()
        base = request.build_absolute_uri(request.path)
        params = q.copy()

        def link(n):
            params["page"] = n
            return f"{base}?{params.urlencode()}"
        facet_people = sorted(set(ChainTx.objects.filter(chain_id=settings.CHAIN_ID).values_list(
            "from_public_id", flat=True)) - {""})
        people.prefetch(facet_people)
        return Response({
            "count": count, "next": link(page + 1) if page * size < count else None,
            "previous": link(page - 1) if page > 1 else None, "results": results,
            "facets": {"contracts": sorted(set(ChainTx.objects.filter(chain_id=settings.CHAIN_ID).exclude(
                contract="").values_list("contract", flat=True))),
                "people": [privacy.person_ref(v, p, people) for p in facet_people]}})
