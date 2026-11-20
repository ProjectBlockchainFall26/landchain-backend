"""Models for `enquiries`. Owner: Person A.

Nothing is built yet. Each block below is the design from docs/api-spec.md section 7
(7.1 = off-chain tables owned by Django, 7.2 = projection tables written only by the indexer).
Field names were frozen in task J1: do not rename them without telling the team.
Only the owner of this app creates its migrations.
"""
from django.db import models  # noqa: F401

# ---- Enquiry  (task A8, Person A) -----------------------------------------------------
# Enquiry                                      # replaces enquiries.ts (localStorage)
#   id                 "enq_" ULID pk
#   parcel_id          varchar(11)
#   record_id          int
#   to_public_id       char(11)                # owner at the time
#   to_profile         fk Profile null         # resolved owner profile (never returned to the sender)
#   from_profile       fk Profile null         # null for anonymous visitors
#   from_public_id     varchar(11) default "public"
#   name               varchar(120)
#   contact            varchar(160)            # phone or email of the enquirer
#   message            text (max 2000)
#   status             enum(new, read, answered)
#   relayed_at         timestamptz null        # email/SMS sent to owner
#   ip_hash            char(64)                # sha256(ip + salt) for rate limiting / abuse
#   created_at, read_at, answered_at

