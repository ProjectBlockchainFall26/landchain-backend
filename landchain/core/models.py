"""Models for `core`. IdempotencyRecord belongs to task D1 (spec section 4)."""
from django.db import models


class IdempotencyRecord(models.Model):
    """First response to a POST with an Idempotency-Key, replayed for 24 h to the same user."""

    profile = models.ForeignKey("accounts.Profile", on_delete=models.CASCADE, related_name="idempotency_records")
    key = models.CharField(max_length=80)
    method = models.CharField(max_length=10)
    path = models.CharField(max_length=300)
    body_hash = models.CharField(max_length=64)
    status_code = models.SmallIntegerField(null=True)
    response = models.JSONField(null=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "idempotency_record"
        constraints = [models.UniqueConstraint(fields=["profile", "key"], name="uniq_idempotency_key")]
