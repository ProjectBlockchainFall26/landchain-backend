"""Models for `registry`. Owner: Person C (models, reads) · B (identity) · D (applications, transfers, review).

Nothing is built yet. Each block below is the design from docs/api-spec.md section 7
(7.1 = off-chain tables owned by Django, 7.2 = projection tables written only by the indexer).
Field names were frozen in task J1: do not rename them without telling the team.
Only the owner of this app creates its migrations.
"""
from django.db import models  # noqa: F401

# ---- ChainIdentity  (task C2, Person C) -----------------------------------------------
# ChainIdentity(address pk, public_id, status, citizen bool, card_hash, updated_at)

# ---- ChainRole  (task C2, Person C) ---------------------------------------------------
# ChainRole(address, role)                                              # registrar | id_officer | admin

# ---- Parcel  (task C2, Person C) ------------------------------------------------------
# Parcel
#   record_id          int pk                  # TitleRegistry record id
#   parcel_id          varchar(11) index       # not unique (rejected ids are reused)
#   is_current         bool index              # latest record for this parcel_id
#   interest           smallint
#   holder, region, location, plan_number, gps_address  varchar
#   acres_x100         int
#   status             smallint
#   owner_address      char(42); owner_public_id char(11)
#   token_id           int null
#   registered_at      timestamptz null; updated_at timestamptz
#   boundary           geometry(Polygon, 4326)   # PostGIS, GIST index
#   lats_micro int[]; lngs_micro int[]
#   created_block, updated_block bigint

# ---- ParcelDoc  (task C2, Person C) ---------------------------------------------------
# ParcelDoc(record_id, position, doc_type, sha256)

# ---- OwnerHistory  (task C2, Person C) ------------------------------------------------
# OwnerHistory(record_id, position, address, public_id)                 # oldest first

# ---- Application  (task C2, Person C) -------------------------------------------------
# Application(app_id pk, record_id, applicant_address, applicant_public_id, created_at,
#             decision, decided_by, decided_at, reason)

# ---- TransferRequest  (task C2, Person C) ---------------------------------------------
# TransferRequest(transfer_id pk, record_id, from_address, from_public_id, to_address, to_public_id,
#                 requested_at, decision, decided_by, decided_at, reason)

# ---- HistoryEvent  (task C2, Person C) ------------------------------------------------
# HistoryEvent(id, record_id, parcel_id, type, text, at, block_number, tx_hash)

