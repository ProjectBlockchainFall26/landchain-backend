"""Models for `accounts`. Owner: Person A.

Nothing is built yet. Each block below is the design from docs/api-spec.md section 7
(7.1 = off-chain tables owned by Django, 7.2 = projection tables written only by the indexer).
Field names were frozen in task J1: do not rename them without telling the team.
Only the owner of this app creates its migrations.
"""
from django.db import models  # noqa: F401

# ---- Profile  (task A2, Person A) -----------------------------------------------------
# Profile
#   id                 uuid pk
#   supabase_user_id   uuid unique            # JWT sub
#   email              citext null
#   phone              varchar(20) null       # E.164
#   full_name          varchar(120)           # never on chain; replaces localStorage "landchain-names"
#   wallet_address     char(42) unique null   # lowercase
#   public_id          char(11) unique null   # GH-xxxxxxxx, derived from wallet_address
#   wallet_linked_at   timestamptz null
#   roles              text[] default {}      # subset of {registrar, id_officer, admin}
#   notify_email       bool default true
#   notify_sms         bool default false
#   is_demo            bool default false
#   created_at, updated_at

# ---- WalletNonce  (task A4, Person A) -------------------------------------------------
# WalletNonce
#   nonce              varchar(32) pk
#   address            char(42)
#   profile            fk Profile
#   message            text                    # exact EIP-4361 text issued
#   expires_at         timestamptz
#   used_at            timestamptz null

