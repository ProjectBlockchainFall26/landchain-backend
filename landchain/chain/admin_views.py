"""Admin chain tools (task B7, spec 9.13): role wallets and signer health."""
from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from rest_framework.response import Response
from rest_framework.views import APIView

from landchain.core.errors import ApiError, SignerUnavailable, Validation
from landchain.core.idempotency import idempotent
from landchain.core.permissions import IsAdmin

from . import client, service
from .encoding import norm_address
from .models import TxIntent

ROLES = ("registrar", "id_officer", "admin")
LOW_BALANCE_ETH = Decimal("0.05")


def signer_rows() -> list[dict]:
    rows = []
    w3 = client.w3()
    acl = client.contract("LandAccessControl")
    for role in ROLES:
        row = {"role": role, "address": None, "balance_eth": None, "pending_nonce": None, "has_role_on_chain": False,
               "queue_depth": TxIntent.objects.filter(status=TxIntent.Status.QUEUED,
                                                      signer_mode=service.SIGNER_MODE[role]).count(),
               "low_balance": False}
        try:
            addr = service.signer_address(role)
            row["address"] = addr
            bal = Decimal(w3.eth.get_balance(client.checksum(addr))) / Decimal(10**18)
            row["balance_eth"] = f"{bal:.2f}"
            row["pending_nonce"] = w3.eth.get_transaction_count(client.checksum(addr), "pending")
            role_id = acl.functions[service.ROLE_CONST[role]]().call()
            row["has_role_on_chain"] = acl.functions.hasRole(role_id, client.checksum(addr)).call()
            row["low_balance"] = settings.CHAIN_ID != 1337 and bal < LOW_BALANCE_ETH
        except ApiError as e:
            row["error"] = e.message
        rows.append(row)
    return rows


class AdminChainRolesView(APIView):
    """POST /api/v1/admin/chain/roles [IsAdmin, LandAccessControl.grantRole / revokeRole]. Task B7."""

    permission_classes = [IsAdmin]

    @idempotent
    def post(self, request, *args, **kwargs):
        from landchain.core.permissions import viewer
        action = str(request.data.get("action", "")).lower()
        role = str(request.data.get("role", "")).upper()
        fe = {}
        if action not in ("grant", "revoke"):
            fe["action"] = ["Use grant or revoke"]
        if role not in ("REGISTRAR_ROLE", "ID_OFFICER_ROLE", "DEFAULT_ADMIN_ROLE"):
            fe["role"] = ["Use REGISTRAR_ROLE, ID_OFFICER_ROLE or DEFAULT_ADMIN_ROLE"]
        try:
            address = norm_address(str(request.data.get("address", "")))
        except ValueError:
            fe["address"] = ["Not an Ethereum address"]
        if fe:
            raise Validation(next(iter(fe.values()))[0], field_errors=fe)
        acl = client.contract("LandAccessControl")
        role_id = acl.functions[role]().call()
        fn = "grantRole" if action == "grant" else "revokeRole"
        intent = service.write(
            signer="admin", contract="LandAccessControl", function=fn, args=[role_id, client.checksum(address)],
            label=f"{role}, {address[:10]}…", success=f"Role {'granted' if action == 'grant' else 'revoked'}",
            by=viewer(request), target=address, request=request,
            idempotency_key=request.headers.get("Idempotency-Key"))
        from .views import intent_response
        return intent_response(request, intent)


class AdminSignersView(APIView):
    """GET /api/v1/admin/signers [IsAdmin]. Task B7."""

    permission_classes = [IsAdmin]

    def get(self, request, *args, **kwargs):
        try:
            return Response({"results": signer_rows()})
        except SignerUnavailable:
            raise
