"""Celery tasks for `chain` (spec section 13)."""
from celery import shared_task


@shared_task(name="signer.send", acks_late=True)
def signer_send(intent_id: str):
    """Re-simulate, sign with the role wallet, send, store the hash. Routed to signer.<role> (concurrency 1)."""
    from .service import send_intent
    intent = send_intent(intent_id)
    return {"intent": intent.id, "status": intent.status, "tx_hash": intent.tx_hash}


@shared_task(name="intents.watch")
def intents_watch():
    """Every 3 s: receipts for submitted intents, expire awaiting_signature after 15 min."""
    from .service import watch_intents
    return watch_intents()


@shared_task(name="signers.health")
def signers_health():
    """Every 5 min: balance and on-chain role of each signer; log an error for admins when unhealthy."""
    import logging

    from .admin_views import signer_rows
    log = logging.getLogger("landchain.chain")
    rows = signer_rows()
    for r in rows:
        if r.get("error") or not r.get("has_role_on_chain") or r.get("low_balance"):
            log.error("Signer unhealthy: %s", r)
    return rows
