"""Models for `chain` (task B3, spec 6.3 and 7.1): every chain write is a TxIntent."""
from django.db import models

from landchain.core.ids import new_txi


class TxIntent(models.Model):
    class Status(models.TextChoices):
        AWAITING_SIGNATURE = "awaiting_signature"
        QUEUED = "queued"
        SUBMITTED = "submitted"
        MINED = "mined"
        CONFIRMED = "confirmed"
        REVERTED = "reverted"
        FAILED = "failed"
        EXPIRED = "expired"

    class Signer(models.TextChoices):
        WALLET = "wallet"
        BACKEND_REGISTRAR = "backend_registrar"
        BACKEND_ID_OFFICER = "backend_id_officer"
        BACKEND_ADMIN = "backend_admin"
        DEV_UNLOCKED = "dev_unlocked"

    FINAL = {"confirmed", "reverted", "failed", "expired"}

    id = models.CharField(max_length=40, primary_key=True, default=new_txi, editable=False)
    chain_id = models.IntegerField()
    action = models.CharField(max_length=40)
    contract = models.CharField(max_length=30)
    function = models.CharField(max_length=40)
    args_json = models.JSONField(default=list)
    args_label = models.CharField(max_length=300, blank=True, default="")
    success_message = models.CharField(max_length=120, blank=True, default="")
    signer_mode = models.CharField(max_length=20, choices=Signer.choices)
    from_address = models.CharField(max_length=42)
    to_address = models.CharField(max_length=42)
    data = models.TextField()
    gas_limit = models.BigIntegerField(default=0)
    status = models.CharField(max_length=20, choices=Status.choices, db_index=True)
    tx_hash = models.CharField(max_length=66, unique=True, null=True, blank=True)
    block_number = models.BigIntegerField(null=True, blank=True)
    revert_reason = models.TextField(null=True, blank=True)
    error = models.TextField(null=True, blank=True)
    result_json = models.JSONField(null=True, blank=True)
    idempotency_key = models.UUIDField(null=True, blank=True)
    created_by = models.ForeignKey("accounts.Profile", on_delete=models.PROTECT, related_name="intents")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "tx_intent"
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["created_by", "idempotency_key"], name="uniq_intent_idem")]

    @property
    def signer_label(self) -> str:
        return self.signer_mode.replace("backend_", "backend:")

    @property
    def is_final(self) -> bool:
        return self.status in self.FINAL


class OfficerAction(models.Model):
    """Who pressed the button: role wallets are shared, so the chain only shows the role."""

    intent = models.ForeignKey(TxIntent, on_delete=models.CASCADE, related_name="officer_actions")
    officer = models.ForeignKey("accounts.Profile", on_delete=models.PROTECT, related_name="officer_actions")
    role = models.CharField(max_length=20)
    action = models.CharField(max_length=40)
    target = models.CharField(max_length=40)
    reason = models.TextField(null=True, blank=True)
    session_id = models.UUIDField(null=True, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "officer_action"
        ordering = ["-created_at"]


class RevertLog(models.Model):
    """Simulation refusals and wallet cancellations, shown in the activity log as Reverted."""

    chain_id = models.IntegerField()
    contract = models.CharField(max_length=30)
    function = models.CharField(max_length=40)
    args_label = models.CharField(max_length=300, blank=True, default="")
    from_address = models.CharField(max_length=42, blank=True, default="")
    from_public_id = models.CharField(max_length=11, blank=True, default="", db_index=True)
    error = models.TextField()
    intent = models.ForeignKey(TxIntent, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "revert_log"
        ordering = ["-created_at"]
