"""One error shape everywhere (spec section 4) and the codes in section 10.1. Task B1.

    {"error": {"code", "message", "revert_reason", "field_errors", "request_id"}}

Raise ApiError (or a subclass) from any view or helper; the exception handler turns it into that shape.
ChainRevert carries the contract's own `require` sentence and picks the HTTP status from section 10.2.
"""
from __future__ import annotations

import logging

from django.core.exceptions import PermissionDenied
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

log = logging.getLogger("landchain.errors")


class ApiError(Exception):
    status_code = 400
    code = "VALIDATION"

    def __init__(self, message: str, *, code: str | None = None, status_code: int | None = None,
                 field_errors: dict | None = None, revert_reason: str | None = None, headers: dict | None = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code
        self.field_errors = field_errors
        self.revert_reason = revert_reason
        self.headers = headers or {}


class Validation(ApiError):
    status_code, code = 400, "VALIDATION"

    def __init__(self, message: str = "Check the highlighted fields.", field_errors: dict | None = None, **kw):
        super().__init__(message, field_errors=field_errors, **kw)


class Forbidden(ApiError):
    status_code, code = 403, "FORBIDDEN"


class Private(ApiError):
    status_code, code = 403, "PRIVATE"


class NotFound(ApiError):
    status_code, code = 404, "NOT_FOUND"


class Conflict(ApiError):
    status_code, code = 409, "CONFLICT"


class ChainUnavailable(ApiError):
    status_code, code = 503, "CHAIN_UNAVAILABLE"


class SignerUnavailable(ApiError):
    status_code, code = 503, "SIGNER_UNAVAILABLE"


# Section 10.2: the HTTP status and code for each `require` sentence. Anything not listed is 422 CHAIN_REVERT.
_REVERT_MAP: list[tuple[str, int, str]] = [
    ("Only an identity officer can do this", 403, "FORBIDDEN"),
    ("Only the registrar can", 403, "FORBIDDEN"),
    ("Only the admin can", 403, "FORBIDDEN"),
    ("Verify your identity before registering land", 403, "IDENTITY_NOT_VERIFIED"),
    ("Application not found", 404, "NOT_FOUND"),
    ("Transfer not found", 404, "NOT_FOUND"),
    ("Parcel does not exist", 404, "NOT_FOUND"),
    ("Payment not found", 404, "NOT_FOUND"),
    ("Card hash is empty", 400, "VALIDATION"),
    ("Parcel ID must look like", 400, "VALIDATION"),
    ("Latitudes and longitudes must pair up", 400, "VALIDATION"),
    ("A boundary needs at least", 400, "VALIDATION"),
    ("A boundary can have at most", 400, "VALIDATION"),
    ("All pillars must be inside Ghana", 400, "VALIDATION"),
    ("Area must be greater than zero", 400, "VALIDATION"),
    ("Name the allodial holder", 400, "VALIDATION"),
    ("Add the regional plan number", 400, "VALIDATION"),
    ("A reason is required to reject", 400, "VALIDATION"),
    ("Amount must be greater than zero", 400, "VALIDATION"),
    ("Add the official receipt number", 400, "VALIDATION"),
]


class ChainRevert(ApiError):
    """The contract refused (simulation or a mined revert). message == revert_reason == the Solidity sentence."""

    status_code, code = 422, "CHAIN_REVERT"

    def __init__(self, reason: str):
        status_code, code = 422, "CHAIN_REVERT"
        for prefix, st, cd in _REVERT_MAP:
            if reason.startswith(prefix):
                status_code, code = st, cd
                break
        super().__init__(reason, code=code, status_code=status_code, revert_reason=reason)


def error_body(code: str, message: str, *, request=None, field_errors=None, revert_reason=None, **extra) -> dict:
    body = {"code": code, "message": message, "revert_reason": revert_reason, "field_errors": field_errors,
            "request_id": getattr(request, "request_id", None) if request is not None else None}
    body.update(extra)
    return {"error": body}


def error_response(exc: ApiError, request=None) -> Response:
    return Response(
        error_body(exc.code, exc.message, request=request, field_errors=exc.field_errors,
                   revert_reason=exc.revert_reason),
        status=exc.status_code, headers=exc.headers or None)


def _flatten(detail) -> dict:
    if isinstance(detail, dict):
        out = {}
        for k, v in detail.items():
            if isinstance(v, dict):
                for kk, vv in _flatten(v).items():
                    out[f"{k}.{kk}"] = vv
            else:
                out[k] = [str(x) for x in (v if isinstance(v, list) else [v])]
        return out
    return {"non_field_errors": [str(x) for x in (detail if isinstance(detail, list) else [detail])]}


def exception_handler(exc, context):
    request = context.get("request")
    if isinstance(exc, ApiError):
        return error_response(exc, request)
    if isinstance(exc, Http404):
        return Response(error_body("NOT_FOUND", str(exc) or "Not found.", request=request), status=404)
    if isinstance(exc, PermissionDenied):
        exc = exceptions.PermissionDenied(str(exc) or None)

    if isinstance(exc, exceptions.ValidationError):
        fe = _flatten(exc.detail)
        first = next(iter(fe.values()), ["Check the highlighted fields."])[0]
        return Response(error_body("VALIDATION", first, request=request, field_errors=fe), status=400)
    if isinstance(exc, exceptions.AuthenticationFailed | exceptions.NotAuthenticated):
        detail = exc.detail
        if isinstance(detail, dict) and "code" in detail:
            code, msg = str(detail["code"]), str(detail.get("message", "Sign in again."))
        else:
            code = "AUTH_REQUIRED" if isinstance(exc, exceptions.NotAuthenticated) else "TOKEN_INVALID"
            msg = "Sign in to do this." if code == "AUTH_REQUIRED" else str(detail)
        return Response(error_body(code, msg, request=request), status=401,
                        headers={"WWW-Authenticate": 'Bearer realm="api"'})
    if isinstance(exc, exceptions.PermissionDenied):
        detail = exc.detail
        if isinstance(detail, dict) and "code" in detail:
            return Response(error_body(str(detail["code"]), str(detail.get("message", "")), request=request),
                            status=403)
        return Response(error_body("FORBIDDEN", str(detail), request=request), status=403)
    if isinstance(exc, exceptions.Throttled):
        wait = int(exc.wait or 60)
        return Response(error_body("RATE_LIMITED", "Too many requests. Try again later.", request=request),
                        status=429, headers={"Retry-After": str(wait)})
    if isinstance(exc, exceptions.UnsupportedMediaType):
        return Response(error_body("UNSUPPORTED_MEDIA_TYPE", str(exc.detail), request=request), status=415)

    response = drf_exception_handler(exc, context)
    if response is not None:
        code = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED", 406: "NOT_ACCEPTABLE",
                400: "VALIDATION"}.get(response.status_code, "ERROR")
        message = exc.detail if isinstance(getattr(exc, "detail", None), str) else str(getattr(exc, "detail", exc))
        response.data = error_body(code, str(message), request=request)
        return response

    log.exception("Unhandled error", exc_info=exc)
    return Response(error_body("INTERNAL", "Something went wrong on our side.", request=request),
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR)
