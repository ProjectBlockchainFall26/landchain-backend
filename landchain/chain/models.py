"""Models for `chain`. Owner: Person B.

Nothing is built yet. Each block below is the design from docs/api-spec.md section 7
(7.1 = off-chain tables owned by Django, 7.2 = projection tables written only by the indexer).
Field names were frozen in task J1: do not rename them without telling the team.
Only the owner of this app creates its migrations.
"""
from django.db import models  # noqa: F401

# ---- TxIntent  (task B3, Person B) ----------------------------------------------------
# TxIntent
#   id                 "txi_" ULID pk
#   chain_id           int
#   action             varchar(40)             # submitProfile, submitApplication, ...
#   contract           varchar(30)
#   function           varchar(40)
#   args_json          jsonb                   # decoded args
#   args_label         varchar(200)            # human label, same as UI's Tx.args
#   signer_mode        enum(wallet, backend_registrar, backend_id_officer, backend_admin, dev_unlocked)
#   from_address       char(42)
#   to_address         char(42)
#   data               text                    # calldata
#   gas_limit          bigint
#   status             enum(awaiting_signature, queued, submitted, mined, confirmed, reverted, failed, expired)
#   tx_hash            char(66) unique null
#   block_number       bigint null
#   revert_reason      text null
#   error              text null
#   result_json        jsonb null              # {app_id, record_id, transfer_id, payment_id}
#   idempotency_key    uuid null
#   created_by         fk Profile
#   created_at, updated_at, expires_at
#   unique (created_by, idempotency_key)

# ---- OfficerAction  (task B3, Person B) -----------------------------------------------
# OfficerAction                                # who pressed the button (role wallets are shared)
#   id, intent fk TxIntent, officer fk Profile, role varchar(20), action varchar(40),
#   target varchar(40)                         # APP-15, TRF-3, GH-…, GA-BRK-0002
#   reason text null, session_id uuid null, ip inet null, created_at

# ---- RevertLog  (task B3, Person B) ---------------------------------------------------
# RevertLog                                    # simulation refusals, shown in the activity log
#   id, chain_id, contract, function, args_label, from_address, from_public_id,
#   error text, intent fk null, created_at

