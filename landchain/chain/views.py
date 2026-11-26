"""GET /config, GET /chain/status (task B6) and the intent endpoints (task B5). Spec 9.1 and 9.9."""
from __future__ import annotations

from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from landchain.core.errors import ApiError, ChainUnavailable, Forbidden, NotFound, Validation
from landchain.core.permissions import IsSignedIn, Public, viewer

from . import client, service
from . import contracts as reg
from .models import TxIntent
from .serializers import intent_obj

CHAIN_NAMES = {1337: "Local Ganache", 11155111: "Sepolia testnet", 1: "Ethereum mainnet"}
EXPLORERS = {11155111: "https://sepolia.etherscan.io"}


def chain_name(chain_id: int | None = None) -> str:
    cid = chain_id or settings.CHAIN_ID
    return CHAIN_NAMES.get(cid, f"Chain {cid}")


def intent_response(request, intent: TxIntent, *, created: bool = False, then=None, extra: dict | None = None):
    """202 (queued) / 201 (prepared), or 200 with the updated objects when ?wait=true and it confirmed."""
    wait = request.query_params.get("wait", "").lower() in ("1", "true", "yes")
    if wait and not created:
        intent = service.wait_for(intent, timeout=30)
    body = {"intent": intent_obj(intent)}
    if extra:
        body.update(extra)
    if intent.status == TxIntent.Status.CONFIRMED and then is not None:
        body.update(then())
    if created:
        code = 201
    else:
        code = 200 if (wait and intent.status == TxIntent.Status.CONFIRMED) else 202
    return Response(body, status=code)


class ConfigView(APIView):
    """GET /api/v1/config [Public]. Task B6."""

    permission_classes = [Public]

    def get(self, request, *args, **kwargs):
        from landchain.documents.models import DOC_TYPES
        try:
            dep = reg.deployment()
            contracts = dep.addresses
            deployment = {"network": dep.network, "start_block": dep.start_block, "deployed_at": dep.deployed_at}
        except reg.ContractsMissing:
            contracts, deployment = {}, None
        local = settings.CHAIN_ID == 1337
        return Response({
            "chain_id": settings.CHAIN_ID, "chain_name": chain_name(), "is_local": local,
            "rpc_url_public": settings.RPC_URL_PUBLIC, "explorer": EXPLORERS.get(settings.CHAIN_ID),
            "contracts": contracts, "deployment": deployment,
            "features": {"dev_unlocked_signing": settings.CHAIN_ALLOW_UNLOCKED_SIGNING,
                         "demo_accounts": bool(local and settings.DEMO_MODE),
                         "sms_relay": bool(settings.SMS_PROVIDER)},
            "doc_types": DOC_TYPES,
            "interests": ["Allodial", "Customary freehold", "Common-law freehold", "Leasehold"],
            "limits": {"min_pillars": 3, "max_pillars": 32, "max_upload_mb": settings.MAX_UPLOAD_MB,
                       "ghana_box": {"min_lat": 4.5, "max_lat": 11.2, "min_lng": -3.3, "max_lng": 1.3}},
        })


class ChainStatusView(APIView):
    """GET /api/v1/chain/status [Public]. Task B6."""

    permission_classes = [Public]

    def get(self, request, *args, **kwargs):
        from landchain.core.middleware import indexed_block
        body = {"kind": "ok", "chain_id": settings.CHAIN_ID, "name": chain_name(), "head_block": None,
                "indexed_block": indexed_block(), "lag_blocks": None, "contracts_match": False, "error": None}
        try:
            head = client.head_block()
            body["head_block"] = head
            if client.chain_id_onchain() != settings.CHAIN_ID:
                raise ChainUnavailable(f"The RPC is on chain {client.chain_id_onchain()}, not {settings.CHAIN_ID}.")
            body["contracts_match"] = client.contracts_match()
            if not body["contracts_match"]:
                raise ChainUnavailable(client.MISSING_CONTRACTS)
            if body["indexed_block"] is not None:
                body["lag_blocks"] = max(0, head - body["indexed_block"])
        except ChainUnavailable as e:
            body["kind"], body["error"] = "error", e.message
        return Response(body)


def _intent_for(request, id: str, *, creator_only: bool) -> TxIntent:
    intent = get_object_or_404(TxIntent, pk=id)
    p = viewer(request)
    if intent.created_by_id != p.pk and (creator_only or not p.is_officer):
        raise NotFound("Transaction not found.")
    return intent


class ChainIntentsDetailView(APIView):
    """GET /api/v1/chain/intents/{id} [creator or IsOfficer]. Task B5."""

    permission_classes = [IsSignedIn]

    def get(self, request, id, *args, **kwargs):
        intent = _intent_for(request, id, creator_only=False)
        if intent.status == TxIntent.Status.SUBMITTED:
            service.poll_receipt(intent)
        elif intent.status == TxIntent.Status.MINED and settings.INDEXER_INLINE:
            service.run_indexer_inline()
            intent.refresh_from_db()
        return Response(intent_obj(intent))


class ChainIntentsDetailSubmittedView(APIView):
    """POST /api/v1/chain/intents/{id}/submitted [creator]. Task B5."""

    permission_classes = [IsSignedIn]

    def post(self, request, id, *args, **kwargs):
        intent = _intent_for(request, id, creator_only=True)
        tx_hash = str(request.data.get("tx_hash") or "").strip().lower()
        import re
        if not re.fullmatch(r"0x[0-9a-f]{64}", tx_hash):
            raise Validation("tx_hash must be a 0x-prefixed 32-byte hash", field_errors={"tx_hash": ["Invalid hash"]})
        return Response(intent_obj(service.verify_submitted(intent, tx_hash)))


class ChainIntentsDetailRejectedByWalletView(APIView):
    """POST /api/v1/chain/intents/{id}/rejected-by-wallet [creator]. Task B5."""

    permission_classes = [IsSignedIn]

    def post(self, request, id, *args, **kwargs):
        intent = _intent_for(request, id, creator_only=True)
        return Response(intent_obj(service.wallet_rejected(intent, request.data.get("message"))))


class ChainIntentsDetailDevSignView(APIView):
    """POST /api/v1/chain/intents/{id}/dev-sign [creator · local chain only]. Task B5."""

    permission_classes = [IsSignedIn]

    def post(self, request, id, *args, **kwargs):
        if not (settings.CHAIN_ALLOW_UNLOCKED_SIGNING and settings.CHAIN_ID == 1337):
            raise NotFound("Not found.")
        intent = _intent_for(request, id, creator_only=True)
        if intent.signer_mode != TxIntent.Signer.WALLET:
            raise Forbidden("Only wallet transactions can be dev-signed.")
        try:
            intent = service.dev_sign(intent)
        except ApiError:
            raise
        if intent.status == TxIntent.Status.MINED and settings.INDEXER_INLINE:
            service.run_indexer_inline()
            intent.refresh_from_db()
        return Response(intent_obj(intent))
