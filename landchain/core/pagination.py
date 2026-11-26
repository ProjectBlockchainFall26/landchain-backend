"""Pagination: {count, next, previous, results}; page_size max 200; ?before=<iso> for infinite scroll. Task C1."""
from __future__ import annotations

from django.utils.dateparse import parse_datetime
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from landchain.core.errors import Validation


class Pagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200

    def get_paginated_response(self, data, **extra):
        body = {"count": self.page.paginator.count, "next": self.get_next_link(),
                "previous": self.get_previous_link(), "results": data}
        body.update(extra)
        return Response(body)


def paginate(request, items, serialize, *, view=None, extra: dict | None = None, page_size: int | None = None):
    """Paginate a queryset or list and return the spec's page body as a Response.

    `serialize(item) -> dict`. `extra` keys are added beside count/next/previous/results.
    """
    p = Pagination()
    if page_size:
        p.page_size = page_size
    page = p.paginate_queryset(items, request, view=view)
    data = [serialize(x) for x in page]
    return p.get_paginated_response(data, **(extra or {}))


def before_filter(request, qs, field: str):
    """Apply ?before=<iso> as `field < before` (activity log, notifications)."""
    raw = request.query_params.get("before")
    if not raw:
        return qs
    dt = parse_datetime(raw.replace(" ", "+"))
    if dt is None:
        raise Validation("before must be an ISO 8601 time", field_errors={"before": ["Use an ISO 8601 time"]})
    return qs.filter(**{f"{field}__lt": dt})


def csv_param(request, name: str, default: str = "") -> list[str]:
    raw = request.query_params.get(name, default) or ""
    return [x.strip() for x in raw.split(",") if x.strip()]
