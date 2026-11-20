"""Models for `indexer`. Owner: Person C.

Nothing is built yet. Each block below is the design from docs/api-spec.md section 7
(7.1 = off-chain tables owned by Django, 7.2 = projection tables written only by the indexer).
Field names were frozen in task J1: do not rename them without telling the team.
Only the owner of this app creates its migrations.
"""
from django.db import models  # noqa: F401

# ---- IndexerCursor  (task C2, Person C) -----------------------------------------------
# IndexerCursor(chain_id pk, title_registry_address, last_block, last_block_hash, updated_at)

# ---- ChainBlock  (task C2, Person C) --------------------------------------------------
# ChainBlock(chain_id, number, hash, timestamp)                         pk (chain_id, number)

# ---- ChainEvent  (task C2, Person C) --------------------------------------------------
# ChainEvent(chain_id, tx_hash, log_index, block_number, contract, event, args jsonb)  unique (chain_id, tx_hash, log_index)

# ---- ChainTx  (task C2, Person C) -----------------------------------------------------
# ChainTx(chain_id, tx_hash pk, from_address, to_address, contract, function, args_label,
#         block_number, at, status "Success", gas_used, effective_gas_price_wei, cost_wei)

