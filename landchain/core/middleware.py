"""Request ids and chain freshness headers (spec section 4). Task B6.

Every read response carries X-Chain-Id, X-Indexed-Block and X-Chain-Head so the UI can show
"indexed up to block N". The chain head is cached for 2 s so a page load costs at most one RPC call.
"""
from __future__ import annotations

from django.conf import settings
from django.core.cache import cache

from landchain.core.ids import new_id


class RequestIdMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = request.headers.get("X-Request-Id") or new_id("req")
        response = self.get_response(request)
        response["X-Request-Id"] = request.request_id
        return response


def cached_head() -> int | None:
    head = cache.get("chain:head")
    if head is None:
        try:
            from landchain.chain import client
            head = client.head_block()
        except Exception:
            head = -1
        cache.set("chain:head", head, 2)
    return None if head == -1 else head


def indexed_block() -> int | None:
    from landchain.indexer.models import IndexerCursor
    cur = IndexerCursor.objects.filter(chain_id=settings.CHAIN_ID).only("last_block").first()
    return cur.last_block if cur and cur.last_block >= 0 else None


class ChainHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.method in ("GET", "HEAD") and request.path.startswith("/api/v1/") \
                and not request.path.startswith("/api/v1/health") and not request.path.startswith("/api/v1/schema") \
                and not request.path.startswith("/api/v1/docs"):
            try:
                response["X-Chain-Id"] = str(settings.CHAIN_ID)
                ib = indexed_block()
                response["X-Indexed-Block"] = "" if ib is None else str(ib)
                head = cached_head()
                response["X-Chain-Head"] = "" if head is None else str(head)
            except Exception:  # headers are best effort; never break a read
                pass
        return response
