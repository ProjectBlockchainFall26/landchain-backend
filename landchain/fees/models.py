"""Models for `fees`. Owner: Person D (C owns the Payment projection + receipt view).

Nothing is built yet. Each block below is the design from docs/api-spec.md section 7
(7.1 = off-chain tables owned by Django, 7.2 = projection tables written only by the indexer).
Field names were frozen in task J1: do not rename them without telling the team.
Only the owner of this app creates its migrations.
"""
from django.db import models  # noqa: F401

# ---- Payment  (task C2, Person C) -----------------------------------------------------
# Payment(payment_id pk, record_id, kind, amount_pesewas, receipt_hash, payer_address, payer_public_id,
#         recorded_by, at, transfer_id null, block_number, tx_hash)

# ---- PaymentReceipt  (task D4, Person D) ----------------------------------------------
# PaymentReceipt                               # private side of a FeeLedger payment
#   payment_id         int pk                  # FeeLedger payment id (after indexing)
#   intent             fk TxIntent unique
#   receipt_no         varchar(64)             # plain receipt number, officers only
#   consideration_ghs  numeric(14,2) null      # price paid, for stamp duty
#   note               text null

