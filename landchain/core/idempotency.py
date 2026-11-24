"""Idempotency-Key handling (task D1, spec section 4).

Same key + same user within 24 h returns the first response instead of doing the work twice. A key reused for
a different request (path or body) is refused with 409 IDEMPOTENCY_CONFLICT. Chain writes also pass the key to
chain.service so the TxIntent itself is unique per (user, key).

    class ApproveView(APIView):
        @idempotent
        def post(self, request, id): ...
"""
from __future__ import annotations

import functools
import hashlib
import json
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.response import Response

from landchain.core.errors import ApiError, Conflict, error_response
from landchain.core.models import IdempotencyRecord
from landchain.core.permissions import viewer

TTL = timedelta(hours=24)


def _body_hash(request) -> str:
    try:
        data = request.data
        if hasattr(data, "dict"):
            data = {k: v for k, v in data.items() if not hasattr(v, "read")}
        raw = json.dumps(data, sort_keys=True, default=str)
    except Exception:
        raw = ""
    return hashlib.sha256(raw.encode()).hexdigest()


def key_of(request) -> str | None:
    k = (request.headers.get("Idempotency-Key") or "").strip()
    return k[:80] or None


def idempotent(view_method):
    @functools.wraps(view_method)
    def wrapper(self, request, *args, **kwargs):
        key, profile = key_of(request), viewer(request)
        if not key or profile is None:
            return view_method(self, request, *args, **kwargs)
        IdempotencyRecord.objects.filter(profile=profile, created_at__lt=timezone.now() - TTL).delete()
        body_hash = _body_hash(request)
        rec = IdempotencyRecord.objects.filter(profile=profile, key=key).first()
        if rec:
            if rec.path != request.path or rec.method != request.method or rec.body_hash != body_hash:
                return error_response(Conflict("This Idempotency-Key was already used for a different request.",
                                               code="IDEMPOTENCY_CONFLICT"), request)
            if rec.status_code is None:
                return error_response(Conflict("The first request with this Idempotency-Key is still running.",
                                               code="IDEMPOTENCY_CONFLICT"), request)
            resp = Response(rec.response, status=rec.status_code)
            resp["Idempotent-Replayed"] = "true"
            return resp
        try:
            with transaction.atomic():
                rec = IdempotencyRecord.objects.create(profile=profile, key=key, method=request.method,
                                                       path=request.path, body_hash=body_hash)
        except IntegrityError:
            return error_response(Conflict("The first request with this Idempotency-Key is still running.",
                                           code="IDEMPOTENCY_CONFLICT"), request)
        try:
            response = view_method(self, request, *args, **kwargs)
        except ApiError as e:  # 4xx refusals (validation, CHAIN_REVERT) are replayed too
            response = error_response(e, request)
        except Exception:
            rec.delete()
            raise
        if isinstance(response, Response) and response.status_code < 500:
            rec.status_code, rec.response = response.status_code, response.data
            rec.save(update_fields=["status_code", "response"])
        else:
            rec.delete()
        return response
    return wrapper
