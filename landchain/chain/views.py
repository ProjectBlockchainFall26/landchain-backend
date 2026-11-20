"""Stub views. Each returns 501 until its task is built. Owners are in the docstrings."""
from rest_framework.views import APIView

from landchain.core.stubs import not_implemented


class ConfigView(APIView):
    """
    GET /api/v1/config  [Public]
        Task B6 (Person B): `GET /config`, `GET /chain/status` + chain freshness headers
        Spec: docs/api-spec.md section 9.1 · Postman: 'GET /config'
        Everything the frontend currently reads from chain/config.ts and
    generated/deployments.json. The UI no longer needs ABIs.
    """

    def get(self, request, *args, **kwargs):
        # TODO(B6): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("B6", request)


class ChainStatusView(APIView):
    """
    GET /api/v1/chain/status  [Public]
        Task B6 (Person B): `GET /config`, `GET /chain/status` + chain freshness headers
        Spec: docs/api-spec.md section 9.1 · Postman: 'GET /chain/status'
        Replaces ChainStatus in store.ts (the banner "Can't reach … Is the chain running?").
    """

    def get(self, request, *args, **kwargs):
        # TODO(B6): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("B6", request)


class ChainIntentsDetailView(APIView):
    """
    GET /api/v1/chain/intents/{id}  [creator or IsOfficer]
        Task B5 (Person B): Intent endpoints + intent watcher
        Spec: docs/api-spec.md section 9.9 · Postman: 'GET /chain/intents/{id}'
        Poll every 1–2 s until confirmed, reverted, failed or expired. Replaces the toast flow
    in chainAct ("Sending to Local Ganache…" → "Confirmed in block 213 · 0x8f1c2a…").
    """

    def get(self, request, *args, **kwargs):
        # TODO(B5): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("B5", request)


class ChainIntentsDetailSubmittedView(APIView):
    """
    POST /api/v1/chain/intents/{id}/submitted  [creator]
        Task B5 (Person B): Intent endpoints + intent watcher
        Spec: docs/api-spec.md section 9.9 · Postman: 'POST /chain/intents/{id}/submitted'
        The UI reports the hash MetaMask returned. The backend checks the transaction matches
    the intent and starts watching its receipt.
    """

    def post(self, request, *args, **kwargs):
        # TODO(B5): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("B5", request)


class ChainIntentsDetailRejectedByWalletView(APIView):
    """
    POST /api/v1/chain/intents/{id}/rejected-by-wallet  [creator]
        Task B5 (Person B): Intent endpoints + intent watcher
        Spec: docs/api-spec.md section 9.9 · Postman: 'POST /chain/intents/{id}/rejected-by-wallet'
        The user cancelled in MetaMask (error code 4001). Marks the intent failed with "You
    cancelled the transaction in your wallet" so it shows in the activity log as the
    frontend does today.
    """

    def post(self, request, *args, **kwargs):
        # TODO(B5): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("B5", request)


class ChainIntentsDetailDevSignView(APIView):
    """
    POST /api/v1/chain/intents/{id}/dev-sign  [creator · local chain only]
        Task B5 (Person B): Intent endpoints + intent watcher
        Spec: docs/api-spec.md section 9.9 · Postman: 'POST /chain/intents/{id}/dev-sign'
        Sends the prepared transaction from Ganache's unlocked account (no wallet). 404 unless
    CHAIN_ALLOW_UNLOCKED_SIGNING=true and chain 1337; 403 CANNOT_SIGN "This account can't
    sign here. Connect it in MetaMask or pick a demo account." if the address isn't
    unlocked.
    """

    def post(self, request, *args, **kwargs):
        # TODO(B5): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("B5", request)

