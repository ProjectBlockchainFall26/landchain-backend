from datetime import UTC, datetime

import pytest
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from landchain.core.pagination import Pagination, parse_before

factory = APIRequestFactory()


def _paginate(query=""):
    request = Request(factory.get("/x" + query))
    p = Pagination()
    page = p.paginate_queryset(list(range(500)), request)
    return p.get_paginated_response(page).data


def test_shape_and_default_page_size():
    data = _paginate()
    assert set(data) == {"count", "next", "previous", "results"}
    assert data["count"] == 500 and len(data["results"]) == 50
    assert data["previous"] is None and data["next"]


def test_page_size_is_capped_at_200():
    assert len(_paginate("?page_size=1000")["results"]) == 200


def test_page_two():
    data = _paginate("?page=2&page_size=10")
    assert data["results"][0] == 10 and data["previous"]


def test_before_absent_is_none():
    assert parse_before(Request(factory.get("/x"))) is None


def test_before_parses_iso_z():
    got = parse_before(Request(factory.get("/x?before=2026-11-19T13:47:15Z")))
    assert got == datetime(2026, 11, 19, 13, 47, 15, tzinfo=UTC)


def test_before_invalid_raises_400():
    with pytest.raises(ValidationError):
        parse_before(Request(factory.get("/x?before=yesterday")))
