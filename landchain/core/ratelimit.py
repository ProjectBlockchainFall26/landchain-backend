"""Rate limits from spec section 4 (task D1), on django-ratelimit's counters.

By user when signed in, by IP when anonymous. Exceeding returns 429 RATE_LIMITED with Retry-After.

    limit(request, "enquiry")       # 5/h and 20/d per IP
"""
from __future__ import annotations

from django.conf import settings
from django_ratelimit.core import get_usage

from landchain.core.errors import ApiError

RULES: dict[str, list[tuple[str, str]]] = {
    # group: [(rate, key)]  key "ip" | "user_or_ip"
    "enquiry": [("5/h", "ip"), ("20/d", "ip")],
    "document_check": [("30/m", "user_or_ip")],
    "prepare": [("20/m", "user_or_ip")],
    "wallet_nonce": [("10/m", "ip")],
}
PERIOD_S = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def client_ip(request) -> str:
    fwd = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return (fwd.split(",")[0].strip() if fwd else "") or request.META.get("REMOTE_ADDR", "") or "unknown"


def _key(kind: str):
    def ip(group, request):
        return client_ip(request)

    def user_or_ip(group, request):
        p = getattr(getattr(request, "user", None), "profile", None)
        return f"user:{p.pk}" if p is not None else f"ip:{client_ip(request)}"
    return ip if kind == "ip" else user_or_ip


def limit(request, group: str):
    if not getattr(settings, "RATELIMIT_ENABLE", True):
        return
    for rate, key in RULES[group]:
        usage = get_usage(request, group=f"{group}:{rate}", key=_key(key), rate=rate, method=["POST", "GET"],
                          increment=True)
        if usage and usage["should_limit"]:
            retry = int(usage.get("time_left") or PERIOD_S[rate[-1]])
            raise ApiError("Too many requests. Try again later.", code="RATE_LIMITED", status_code=429,
                           headers={"Retry-After": str(max(1, retry))})
