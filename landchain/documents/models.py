"""Models for `documents`. Owner: Person D.

Nothing is built yet. Each block below is the design from docs/api-spec.md section 7
(7.1 = off-chain tables owned by Django, 7.2 = projection tables written only by the indexer).
Field names were frozen in task J1: do not rename them without telling the team.
Only the owner of this app creates its migrations.
"""
from django.db import models  # noqa: F401

# ---- Document  (task D2, Person D) ----------------------------------------------------
# Document                                     # replaces vault.ts (IndexedDB)
#   id                 "doc_" ULID pk
#   sha256             char(66) index          # 0x + 64 hex, equals on-chain Doc.hash
#   doc_type           varchar(40)             # Site plan | Indenture | Search report | Consent / concurrence
#   original_name      varchar(255)            # private: may contain a person's name
#   mime               varchar(80)
#   size_bytes         int
#   storage_path       varchar(300)            # parcel-documents/<sha256>
#   uploaded_by        fk Profile
#   status             enum(staged, attached, orphaned)
#   parcel_record_id   int null                # set when the indexer sees the fingerprint on a record
#   created_at, attached_at
#   unique (sha256, uploaded_by)

