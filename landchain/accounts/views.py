"""GET/PATCH /me (task A3) and wallet linking with Sign-In with Ethereum (task A4). Spec 5.4 and 9.2."""
from __future__ import annotations

import re
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from eth_account import Account
from eth_account.messages import encode_defunct
from rest_framework.response import Response
from rest_framework.views import APIView

from landchain.chain.encoding import iso, norm_address, public_id
from landchain.core.errors import ApiError, Conflict, Validation
from landchain.core.permissions import IsSignedIn, viewer
from landchain.core.ratelimit import limit

from .models import Profile, WalletNonce
from .serializers import me_obj

PHONE_RE = re.compile(r"^\+\d{8,15}$")
NONCE_TTL = timedelta(minutes=10)


class MeView(APIView):
    """GET / PATCH /api/v1/me [IsSignedIn]."""

    permission_classes = [IsSignedIn]

    def get(self, request, *args, **kwargs):
        return Response(me_obj(viewer(request)))

    def patch(self, request, *args, **kwargs):
        p = viewer(request)
        d, fe, fields = request.data, {}, []
        if "full_name" in d:
            name = str(d.get("full_name") or "").strip()
            if not 2 <= len(name) <= 120:
                fe["full_name"] = ["Name must be 2 to 120 characters"]
            p.full_name = name
            fields.append("full_name")
        if "phone" in d:
            phone = re.sub(r"[\s-]", "", str(d.get("phone") or ""))
            if phone and not PHONE_RE.match(phone):
                fe["phone"] = ["Use the international format, e.g. +233240000000"]
            if phone.startswith("+233") and not re.fullmatch(r"\+233\d{9}", phone):
                fe["phone"] = ["A Ghana number is +233 followed by 9 digits"]
            p.phone = phone or None
            fields.append("phone")
        notify = d.get("notify")
        if isinstance(notify, dict):
            if "email" in notify:
                p.notify_email = bool(notify["email"])
                fields.append("notify_email")
            if "sms" in notify:
                p.notify_sms = bool(notify["sms"])
                fields.append("notify_sms")
        if fe:
            raise Validation(next(iter(fe.values()))[0], field_errors=fe)
        if fields:
            p.save(update_fields=[*fields, "updated_at"])
        return Response(me_obj(p))


def siwe_message(address_checksum: str, nonce: str, issued, expires) -> str:
    """Exact EIP-4361 text (spec 9.2)."""
    return (f"{settings.SITE_DOMAIN} wants you to sign in with your Ethereum account:\n{address_checksum}\n\n"
            "Link this wallet to your LandChain account. This does not send a transaction or cost anything.\n\n"
            f"URI: {settings.SITE_URI}\nVersion: 1\nChain ID: {settings.CHAIN_ID}\nNonce: {nonce}\n"
            f"Issued At: {iso(issued)}\nExpiration Time: {iso(expires)}")


def _check_linkable(profile, address: str):
    if profile.wallet_address:
        if profile.wallet_address == address:
            return
        raise Conflict("Your account already has a linked wallet.", code="WALLET_ALREADY_LINKED")
    if Profile.objects.filter(wallet_address=address).exclude(pk=profile.pk).exists():
        raise Conflict("This wallet is linked to another LandChain account.", code="WALLET_IN_USE")


def _is_officer_wallet(address: str) -> bool:
    from landchain.chain import client
    from landchain.registry.models import ChainRole
    if ChainRole.objects.filter(address=address, role__in=["registrar", "id_officer"]).exists():
        return True
    try:
        return bool(client.contract("LandAccessControl").functions.isOfficer(client.checksum(address)).call())
    except ApiError:
        return False


class AuthWalletNonceView(APIView):
    """POST /api/v1/auth/wallet/nonce [IsSignedIn]."""

    permission_classes = [IsSignedIn]

    def post(self, request, *args, **kwargs):
        limit(request, "wallet_nonce")
        p = viewer(request)
        try:
            address = norm_address(str(request.data.get("address", "")))
        except ValueError:
            raise Validation("Not an Ethereum address", field_errors={"address": ["Not an Ethereum address"]}) \
                from None
        if p.wallet_address and p.wallet_address != address:
            raise Conflict("Your account already has a linked wallet.", code="WALLET_ALREADY_LINKED")
        _check_linkable(p, address)
        now = timezone.now().replace(microsecond=0)
        nonce = secrets.token_urlsafe(12)[:16].replace("-", "x").replace("_", "y")
        expires = now + NONCE_TTL
        msg = siwe_message(_checksum(address), nonce, now, expires)
        WalletNonce.objects.create(nonce=nonce, address=address, profile=p, message=msg, expires_at=expires)
        return Response({"nonce": nonce, "expires_at": iso(expires), "message": msg})


def _checksum(address: str) -> str:
    from web3 import Web3
    return Web3.to_checksum_address(address)


class AuthWalletVerifyView(APIView):
    """POST /api/v1/auth/wallet/verify [IsSignedIn]."""

    permission_classes = [IsSignedIn]

    def post(self, request, *args, **kwargs):
        p = viewer(request)
        message = str(request.data.get("message", ""))
        signature = str(request.data.get("signature", ""))
        m = re.search(r"\nNonce: (\S+)\n", message)
        with transaction.atomic():
            n = WalletNonce.objects.select_for_update().filter(nonce=m.group(1) if m else "", profile=p).first()
            if n is None or n.used_at is not None or n.expires_at < timezone.now() or n.message != message:
                raise ApiError("This sign-in request is unknown, used or expired. Start again.",
                               code="NONCE_INVALID", status_code=400)
            try:
                signer = Account.recover_message(encode_defunct(text=message), signature=signature).lower()
            except Exception:
                signer = None
            if signer != n.address:
                raise ApiError("The signature doesn't match this wallet.", code="SIGNATURE_INVALID", status_code=400)
            _check_linkable(p, n.address)
            if _is_officer_wallet(n.address):
                raise Conflict("This wallet holds a Lands Commission role on chain, so it can't be a citizen wallet.",
                               code="WALLET_IS_OFFICER")
            n.used_at = timezone.now()
            n.save(update_fields=["used_at"])
            p.wallet_address, p.public_id, p.wallet_linked_at = n.address, public_id(n.address), timezone.now()
            p.save(update_fields=["wallet_address", "public_id", "wallet_linked_at", "updated_at"])
        body = me_obj(p)
        live = _live_identity(n.address)
        if live is not None and body["identity"]["status"] == "none":
            body["identity"].update(live)
        return Response(body)


def _live_identity(address: str) -> dict | None:
    """Read profileOf straight from the chain so /me shows the identity before the indexer catches up."""
    from landchain.chain import client
    from landchain.chain.encoding import IDENTITY_STATUS, hex0x, ts_to_dt
    try:
        status, citizen, card, updated = client.contract("IdentityRegistry").functions.profileOf(
            client.checksum(address)).call()
    except Exception:
        return None
    if not status:
        return None
    return {"status": IDENTITY_STATUS[status], "citizenship": "citizen" if citizen else "non-citizen",
            "card_hash": hex0x(card), "updated_at": iso(ts_to_dt(updated))}
