"""Encoding rules shared with the frontend and the contracts. Task B2, spec 6.4.

Every helper here must give exactly what landchain-web and the Solidity code compute.
"""
from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from eth_utils import is_address
from web3 import Web3

# ---- enums (on-chain index <-> API string)
IDENTITY_STATUS = ["none", "pending", "verified", "rejected"]
INTEREST = ["Allodial", "Customary freehold", "Common-law freehold", "Leasehold"]
PARCEL_STATUS = ["pending", "registered", "transfer_pending", "rejected"]
PARCEL_STATUS_LABEL = {"pending": "Pending", "registered": "Registered",
                       "transfer_pending": "Transfer pending", "rejected": "Rejected"}
DECISION = ["waiting", "approved", "rejected", "cancelled"]
FEE_KINDS = ["Official search", "Stamp duty", "First registration", "Transfer"]

# Ghana box in micro-degrees (TitleRegistry MIN_LAT … MAX_LNG)
MIN_LAT, MAX_LAT, MIN_LNG, MAX_LNG = 4_500_000, 11_200_000, -3_300_000, 1_300_000
MIN_PILLARS, MAX_PILLARS = 3, 32

PARCEL_ID_RE = re.compile(r"[A-Z]{2}-[A-Z]{3}-\d{4}")
GPS_RE = re.compile(r"[A-Z]{2}-\d{3,4}-\d{4}")
CARD_RE = re.compile(r"GHA-\d{9}-\d")
PUBLIC_ID_RE = re.compile(r"GH-[0-9a-f]{8}")
HASH32_RE = re.compile(r"0x[0-9a-f]{64}")

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
ZERO_HASH = "0x" + "00" * 32


def hex0x(b) -> str:
    """bytes/HexBytes/str -> lowercase 0x hex."""
    if isinstance(b, str):
        return b.lower() if b.startswith("0x") else "0x" + b.lower()
    return "0x" + bytes(b).hex()


def norm_address(addr: str) -> str:
    if not addr or not is_address(addr):
        raise ValueError("Not an Ethereum address")
    return addr.lower()


def public_id(address: str) -> str:
    """"GH-" + first 4 bytes of keccak256 of the 20 address bytes (= IdentityRegistry.publicIdOf)."""
    return "GH-" + Web3.keccak(hexstr=address.lower()).hex().removeprefix("0x")[:8]


def card_hash(card: str) -> str:
    return hex0x(Web3.keccak(text="landchain-card:" + re.sub(r"\s+", "", card.strip().upper())))


def receipt_hash(receipt_no: str) -> str:
    return hex0x(Web3.keccak(text=receipt_no.strip().upper()))


def file_fingerprint(data: bytes) -> str:
    return "0x" + hashlib.sha256(data).hexdigest()


def to_micro(deg: float) -> int:
    # round half away from zero, like JS Math.round for positives; matches round(lat * 1e6) closely enough
    return int(Decimal(str(deg)).scaleb(6).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def from_micro(v: int) -> float:
    return round(v / 1_000_000, 6)


def pesewas(ghs) -> int:
    return int((Decimal(str(ghs)) * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def ghs_str(pesewas_amount: int) -> str:
    return f"{Decimal(pesewas_amount) / 100:.2f}"


def cedi(pesewas_amount: int) -> str:
    """'GH¢ 1,178.00' (frontend cedi())."""
    return f"GH¢ {Decimal(pesewas_amount) / 100:,.2f}"


def acres_str(acres_x100: int) -> str:
    return f"{Decimal(acres_x100) / 100:.2f}"


def ts_to_dt(seconds: int | None) -> datetime | None:
    if not seconds:
        return None
    return datetime.fromtimestamp(int(seconds), tz=UTC)


def iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def interest_index(name: str) -> int:
    for i, n in enumerate(INTEREST):
        if n.lower() == (name or "").strip().lower():
            return i
    raise ValueError("Unknown interest")


def fee_kind_index(kind) -> int:
    if isinstance(kind, int) or (isinstance(kind, str) and kind.isdigit()):
        i = int(kind)
        if 0 <= i < len(FEE_KINDS):
            return i
        raise ValueError("Unknown fee kind")
    for i, n in enumerate(FEE_KINDS):
        if n.lower() == (kind or "").strip().lower():
            return i
    raise ValueError("Unknown fee kind")


def short_hash(h: str, n: int = 10) -> str:
    return f"{h[:n]}…"
