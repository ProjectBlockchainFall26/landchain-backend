"""Query helpers shared by every app (task C5): current_parcel(parcel_id) etc."""
from __future__ import annotations

from landchain.core.errors import NotFound

from .models import Application, ChainIdentity, Parcel, TransferRequest


def normalize_parcel_id(parcel_id: str) -> str:
    return (parcel_id or "").strip().upper()


def current_parcel(parcel_id: str, *, record_id: int | None = None, missing: str | None = None) -> Parcel:
    """Latest record for a parcel ID (a rejected application frees the ID, so there may be several)."""
    pid = normalize_parcel_id(parcel_id)
    qs = Parcel.objects.filter(parcel_id=pid)
    p = qs.filter(record_id=record_id).first() if record_id else qs.order_by("-record_id").first()
    if p is None:
        raise NotFound(missing or f"No parcel called {pid}.")
    return p


def latest_application(parcel: Parcel) -> Application | None:
    return parcel.applications.order_by("-app_id").first()


def open_transfer(parcel: Parcel) -> TransferRequest | None:
    return parcel.transfers.filter(decision=0).order_by("-transfer_id").first()


def identity_of(address: str | None) -> ChainIdentity | None:
    if not address:
        return None
    return ChainIdentity.objects.filter(address=address.lower()).first()


def identity_by_public_id(public_id: str) -> ChainIdentity | None:
    return ChainIdentity.objects.filter(public_id=(public_id or "").lower().replace("gh-", "GH-")).first()


def address_for_public_id(public_id: str) -> str | None:
    """Resolve GH-xxxxxxxx to an address: on-chain identities first, then linked profiles."""
    from landchain.accounts.models import Profile
    pid = "GH-" + (public_id or "").strip()[3:].lower()
    ci = ChainIdentity.objects.filter(public_id=pid).first()
    if ci:
        return ci.address
    p = Profile.objects.filter(public_id=pid).exclude(wallet_address__isnull=True).first()
    return p.wallet_address if p else None


def parcels_owned_by(public_id: str):
    return Parcel.objects.filter(is_current=True, owner_public_id=public_id, status__in=[1, 2])
