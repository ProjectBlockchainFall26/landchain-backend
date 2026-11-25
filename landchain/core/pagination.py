"""C1 (Person C): pagination for every list endpoint (spec section 4).

Response shape: {"count", "next", "previous", "results"}.
Query: ?page=1&page_size=50 (max 200).
The activity log and notifications also accept ?before=<iso timestamp> (infinite scroll):
use `apply_before(queryset, request, "at")` in those views before paginating.
"""
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination


class Pagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200


def parse_before(request):
    """Return the ?before= value as an aware datetime, or None if it is absent.

    Raises ValidationError (400) if the value is not an ISO 8601 timestamp.
    """
    raw = request.query_params.get("before")
    if not raw:
        return None
    value = parse_datetime(raw.replace(" ", "+")) if raw else None  # "+" can arrive as a space in URLs
    if value is None:
        raise ValidationError({"before": "Must be an ISO 8601 timestamp, e.g. 2026-11-19T13:47:15Z"})
    return value


def apply_before(queryset, request, field="at"):
    """Keep only rows strictly older than ?before= (no-op when the parameter is absent)."""
    before = parse_before(request)
    if before is None:
        return queryset
    return queryset.filter(**{f"{field}__lt": before})
