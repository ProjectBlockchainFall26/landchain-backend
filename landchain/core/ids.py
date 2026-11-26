"""Prefixed ULIDs for backend objects and parsing of on-chain ids (spec section 4). Task B1."""
from __future__ import annotations

import re

from ulid import ULID

from landchain.core.errors import NotFound

PREFIXES = {"intent": "txi", "document": "doc", "enquiry": "enq", "notification": "ntf"}


def new_id(prefix: str) -> str:
    """new_id("txi") -> "txi_01JD3K8W5Q9Y2M7T4R6V1B0C3N"."""
    return f"{prefix}_{ULID()}"


def ulid_default(prefix: str):
    """Callable for a model field default: `default=ulid_default("doc")`."""
    def make() -> str:
        return new_id(prefix)
    make.__name__ = f"new_{prefix}_id"
    make.__qualname__ = make.__name__
    return make


def new_txi() -> str:
    return new_id("txi")


def new_doc() -> str:
    return new_id("doc")


def new_enq() -> str:
    return new_id("enq")


def new_ntf() -> str:
    return new_id("ntf")


_ONCHAIN = {"APP", "TRF", "PAY"}


def parse_id(value, prefix: str, *, what: str | None = None) -> int:
    """Accepts "APP-7", "app-7" or "7" (and an int). Raises 404 NOT_FOUND for anything else."""
    assert prefix in _ONCHAIN
    s = str(value).strip()
    m = re.fullmatch(rf"(?:{prefix}-)?(\d+)", s, flags=re.I)
    if not m or int(m.group(1)) <= 0:
        raise NotFound(f"{what or prefix} {s} not found")
    return int(m.group(1))


def fmt_app(app_id: int | None) -> str | None:
    return f"APP-{app_id}" if app_id else None


def fmt_trf(transfer_id: int | None) -> str | None:
    return f"TRF-{transfer_id}" if transfer_id else None


def fmt_pay(payment_id: int | None) -> str | None:
    return f"PAY-{payment_id}" if payment_id else None
