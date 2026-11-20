"""Models for `notifications`. Owner: Person A.

Nothing is built yet. Each block below is the design from docs/api-spec.md section 7
(7.1 = off-chain tables owned by Django, 7.2 = projection tables written only by the indexer).
Field names were frozen in task J1: do not rename them without telling the team.
Only the owner of this app creates its migrations.
"""
from django.db import models  # noqa: F401

# ---- Notification  (task A7, Person A) ------------------------------------------------
# Notification
#   id                 "ntf_" ULID pk
#   recipient_public_id varchar(11) null       # for a citizen
#   recipient_role     varchar(20) null        # "registrar" | "id_officer" (UI's "role:Registrar")
#   recipient_profile  fk Profile null
#   kind               varchar(40)             # see section 12
#   text               varchar(300)
#   parcel_id          varchar(11) null
#   link               varchar(120) null       # "/title/GA-BRK-0006", "/review"
#   source_event       fk ChainEvent null
#   at                 timestamptz
#   NotificationRead(notification, profile, read_at)  # role notifications are read per officer

