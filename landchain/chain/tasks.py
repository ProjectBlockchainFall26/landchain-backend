"""Celery tasks for `chain` (spec section 13). Celery itself is wired up in B1."""

# TODO(B4, Person B): task 'signer.send': Re-simulate, sign with the role wallet, send, store the hash (queues signer.registrar, signer.id_officer, signer.admin; concurrency 1).
# TODO(B5, Person B): task 'intents.watch': Every 3 s: receipts for submitted intents, expire awaiting_signature after 15 min.
# TODO(B7, Person B): task 'signers.health': Every 5 min: balance and on-chain role of each signer.
