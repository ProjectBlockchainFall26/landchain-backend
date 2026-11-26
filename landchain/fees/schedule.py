"""Fee schedule and estimates, a port of the frontend's fees.ts (task D3, spec 9.7). Estimates only."""
from __future__ import annotations

import math
from decimal import ROUND_HALF_UP, Decimal

from landchain.chain.encoding import FEE_KINDS

SOURCE = ("Lands Commission fee schedule as reported by YEN.com.gh (27 Oct 2026). Stamp Duty Act 2005 (Act 689) "
          "as amended by Act 1109. Estimates: confirm with the Lands Commission and the GRA.")

FEE_INFO = {
    "Official search": {"paid_to": "Lands Commission", "how": "GH¢ 163 for a land certificate search",
                        "required_for": []},
    "Stamp duty": {"paid_to": "Ghana Revenue Authority",
                   "how": "0.25% up to GH¢ 10,000, 0.5% up to GH¢ 50,000, 1% above, of the price paid",
                   "required_for": ["registration"]},
    "First registration": {"paid_to": "Lands Commission", "how": "GH¢ 1,148–1,178 per acre or part of an acre",
                           "required_for": ["registration"]},
    "Transfer": {"paid_to": "Lands Commission", "how": "GH¢ 973 per acre or part of an acre",
                 "required_for": ["transfer"]},
}
REGISTRATION_REQUIRED = ["Stamp duty", "First registration"]


def schedule() -> dict:
    return {"kinds": [{"kind": k, "index": i, **FEE_INFO[k]} for i, k in enumerate(FEE_KINDS)], "source": SOURCE}


def _per_acre(rate: int, acres: float) -> int:
    return rate * max(1, math.ceil(acres))


def stamp_duty(consideration: Decimal) -> int:
    rate = Decimal("0.0025") if consideration <= 10_000 else (Decimal("0.005") if consideration < 50_000
                                                             else Decimal("0.01"))
    return int((consideration * rate).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _rate_text(consideration: Decimal) -> str:
    return "0.25%" if consideration <= 10_000 else ("0.5%" if consideration < 50_000 else "1%")


def estimate(kind: str, acres: float | None = None, consideration: Decimal | None = None) -> dict:
    """{"kind", "suggested_ghs", "suggested_pesewas", "basis"}; suggested_* is None when it can't be estimated."""
    acres = float(acres or 0)
    if kind == "Official search":
        ghs, basis = 163, "Fixed fee for an official search"
    elif kind == "Stamp duty":
        if not consideration:
            return {"kind": kind, "suggested_ghs": None, "suggested_pesewas": None,
                    "basis": "Needs the price paid (consideration)"}
        ghs = stamp_duty(consideration)
        basis = f"{_rate_text(consideration)} of GH¢ {consideration:,.2f}"
    elif kind == "First registration":
        n = max(1, math.ceil(acres))
        ghs, basis = _per_acre(1178, acres), f"GH¢ 1,178 × {n} acre{'s' if n != 1 else ''} or part"
    elif kind == "Transfer":
        n = max(1, math.ceil(acres))
        ghs, basis = _per_acre(973, acres), f"GH¢ 973 × {n} acre{'s' if n != 1 else ''} or part"
    else:
        raise ValueError("Unknown fee kind")
    return {"kind": kind, "suggested_ghs": f"{Decimal(ghs):.2f}", "suggested_pesewas": ghs * 100, "basis": basis}
