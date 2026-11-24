"""TxIntent shape (spec 8)."""
from __future__ import annotations

from landchain.chain.encoding import iso

from .models import TxIntent


def intent_obj(intent: TxIntent) -> dict:
    from .service import unsigned_tx
    return {
        "id": intent.id,
        "action": intent.action,
        "contract": intent.contract,
        "function": intent.function,
        "args_label": intent.args_label,
        "signer": intent.signer_label,
        "status": intent.status,
        "from": intent.from_address,
        "tx": unsigned_tx(intent) if intent.status == TxIntent.Status.AWAITING_SIGNATURE else None,
        "tx_hash": intent.tx_hash,
        "block": intent.block_number,
        "revert_reason": intent.revert_reason,
        "error": intent.error,
        "result": intent.result_json,
        "success_message": intent.success_message,
        "created_at": iso(intent.created_at),
        "updated_at": iso(intent.updated_at),
        "expires_at": iso(intent.expires_at),
    }
