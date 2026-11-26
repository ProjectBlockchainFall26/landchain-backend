"""Projection models for `registry` (task C2, spec 7.2). Written only by the indexer; API views never write here.

Every row can be rebuilt from the contracts' view functions (`POST /admin/indexer/resync`).
"""
from django.contrib.gis.db import models as gis
from django.contrib.postgres.fields import ArrayField
from django.db import models

from landchain.chain.encoding import DECISION, IDENTITY_STATUS, INTEREST, PARCEL_STATUS


class ChainIdentity(models.Model):
    """IdentityRegistry.profileOf(address)."""

    address = models.CharField(max_length=42, primary_key=True)
    public_id = models.CharField(max_length=11, unique=True)
    status = models.SmallIntegerField(default=0)            # IdentityRegistry.Status
    citizen = models.BooleanField(default=True)
    card_hash = models.CharField(max_length=66, blank=True, default="")
    submitted_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "chain_identity"

    @property
    def status_name(self) -> str:
        return IDENTITY_STATUS[self.status]


class ChainRole(models.Model):
    """Role wallets on LandAccessControl: registrar | id_officer | admin."""

    address = models.CharField(max_length=42)
    role = models.CharField(max_length=20)

    class Meta:
        db_table = "chain_role"
        constraints = [models.UniqueConstraint(fields=["address", "role"], name="uniq_chain_role")]


class Parcel(models.Model):
    record_id = models.IntegerField(primary_key=True)          # TitleRegistry record id
    parcel_id = models.CharField(max_length=11, db_index=True)  # not unique: rejected ids are reused
    is_current = models.BooleanField(default=True, db_index=True)
    interest = models.SmallIntegerField(default=0)
    holder = models.CharField(max_length=200, blank=True, default="")
    region = models.CharField(max_length=100, blank=True, default="")
    location = models.CharField(max_length=200, blank=True, default="")
    plan_number = models.CharField(max_length=100, blank=True, default="")
    gps_address = models.CharField(max_length=40, blank=True, default="")
    acres_x100 = models.IntegerField(default=0)
    status = models.SmallIntegerField(default=0, db_index=True)
    owner_address = models.CharField(max_length=42, db_index=True)
    owner_public_id = models.CharField(max_length=11, db_index=True)
    applicant_address = models.CharField(max_length=42, blank=True, default="")
    applicant_public_id = models.CharField(max_length=11, blank=True, default="")
    token_id = models.IntegerField(null=True, blank=True)
    registered_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)
    boundary = gis.PolygonField(srid=4326, null=True, blank=True)     # GIST index by default
    lats_micro = ArrayField(models.IntegerField(), default=list)
    lngs_micro = ArrayField(models.IntegerField(), default=list)
    created_block = models.BigIntegerField(default=0)
    updated_block = models.BigIntegerField(default=0)

    class Meta:
        db_table = "parcel"
        ordering = ["parcel_id"]

    @property
    def status_name(self) -> str:
        return PARCEL_STATUS[self.status]

    @property
    def interest_name(self) -> str:
        return INTEREST[self.interest] if 0 <= self.interest < len(INTEREST) else str(self.interest)

    @property
    def pillars(self) -> list[list[float]]:
        return [[round(a / 1e6, 6), round(b / 1e6, 6)] for a, b in zip(self.lats_micro, self.lngs_micro, strict=False)]

    @property
    def owner_public_ids(self) -> list[str]:
        return [o.public_id for o in self.owners.all()]


class ParcelDoc(models.Model):
    parcel = models.ForeignKey(Parcel, on_delete=models.CASCADE, related_name="docs", db_column="record_id")
    position = models.SmallIntegerField()
    doc_type = models.CharField(max_length=60)
    sha256 = models.CharField(max_length=66, db_index=True)

    class Meta:
        db_table = "parcel_doc"
        ordering = ["position"]
        constraints = [models.UniqueConstraint(fields=["parcel", "position"], name="uniq_parcel_doc_pos")]


class OwnerHistory(models.Model):
    """Every owner of a record, oldest first (TitleRegistry.ownerHistory)."""

    parcel = models.ForeignKey(Parcel, on_delete=models.CASCADE, related_name="owners", db_column="record_id")
    position = models.SmallIntegerField()
    address = models.CharField(max_length=42)
    public_id = models.CharField(max_length=11, db_index=True)

    class Meta:
        db_table = "owner_history"
        ordering = ["position"]
        constraints = [models.UniqueConstraint(fields=["parcel", "position"], name="uniq_owner_pos")]


class Application(models.Model):
    app_id = models.IntegerField(primary_key=True)
    parcel = models.ForeignKey(Parcel, on_delete=models.CASCADE, related_name="applications", db_column="record_id")
    applicant_address = models.CharField(max_length=42)
    applicant_public_id = models.CharField(max_length=11, db_index=True)
    created_at = models.DateTimeField(null=True)
    decision = models.SmallIntegerField(default=0, db_index=True)
    decided_by = models.CharField(max_length=42, blank=True, default="")
    decided_at = models.DateTimeField(null=True, blank=True)
    reason = models.TextField(blank=True, default="")

    class Meta:
        db_table = "application"
        ordering = ["app_id"]

    @property
    def decision_name(self) -> str:
        return DECISION[self.decision]

    @property
    def record_id(self) -> int:
        return self.parcel_id


class TransferRequest(models.Model):
    transfer_id = models.IntegerField(primary_key=True)
    parcel = models.ForeignKey(Parcel, on_delete=models.CASCADE, related_name="transfers", db_column="record_id")
    from_address = models.CharField(max_length=42)
    from_public_id = models.CharField(max_length=11, db_index=True)
    to_address = models.CharField(max_length=42)
    to_public_id = models.CharField(max_length=11, db_index=True)
    requested_at = models.DateTimeField(null=True)
    decision = models.SmallIntegerField(default=0, db_index=True)
    decided_by = models.CharField(max_length=42, blank=True, default="")
    decided_at = models.DateTimeField(null=True, blank=True)
    reason = models.TextField(blank=True, default="")

    class Meta:
        db_table = "transfer_request"
        ordering = ["transfer_id"]

    @property
    def decision_name(self) -> str:
        return DECISION[self.decision]

    @property
    def record_id(self) -> int:
        return self.parcel_id


class HistoryEvent(models.Model):
    """Title history lines, same texts as the frontend's snapshot.ts."""

    record_id = models.IntegerField(db_index=True)
    parcel_id = models.CharField(max_length=11, db_index=True)
    type = models.CharField(max_length=40)
    text = models.CharField(max_length=300)
    at = models.DateTimeField(null=True)
    block_number = models.BigIntegerField()
    log_index = models.IntegerField(default=0)
    tx_hash = models.CharField(max_length=66)

    class Meta:
        db_table = "history_event"
        ordering = ["block_number", "log_index"]
        constraints = [models.UniqueConstraint(fields=["tx_hash", "log_index"], name="uniq_history_log")]
