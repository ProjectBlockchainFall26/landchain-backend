"""Models for `notifications` (task A7). Rows are created by the indexer (C8) and by enquiries (A8)."""
from django.db import models

from landchain.core.ids import new_ntf

ROLE_AUDIENCE = {"registrar": "role:Registrar", "id_officer": "role:Identity officer"}


class Notification(models.Model):
    id = models.CharField(max_length=40, primary_key=True, default=new_ntf, editable=False)
    recipient_public_id = models.CharField(max_length=11, null=True, blank=True, db_index=True)
    recipient_role = models.CharField(max_length=20, null=True, blank=True, db_index=True)
    recipient_profile = models.ForeignKey("accounts.Profile", null=True, blank=True, on_delete=models.CASCADE,
                                          related_name="notifications")
    kind = models.CharField(max_length=40)
    text = models.CharField(max_length=300)
    parcel_id = models.CharField(max_length=11, null=True, blank=True)
    link = models.CharField(max_length=120, null=True, blank=True)
    source_event = models.ForeignKey("indexer.ChainEvent", null=True, blank=True, on_delete=models.SET_NULL)
    dedupe_key = models.CharField(max_length=120, null=True, blank=True, unique=True)  # replays never duplicate
    relay = models.BooleanField(default=False)
    relay_extra = models.TextField(null=True, blank=True)       # e.g. enquiry message + contact for the owner
    relayed_at = models.DateTimeField(null=True, blank=True)
    at = models.DateTimeField(db_index=True)

    class Meta:
        db_table = "notification"
        ordering = ["-at", "-id"]

    @property
    def audience(self) -> str:
        if self.recipient_role:
            return ROLE_AUDIENCE.get(self.recipient_role, f"role:{self.recipient_role}")
        return "me"


class NotificationRead(models.Model):
    """Role notifications are read per officer, so read state lives here."""

    notification = models.ForeignKey(Notification, on_delete=models.CASCADE, related_name="reads")
    profile = models.ForeignKey("accounts.Profile", on_delete=models.CASCADE, related_name="notification_reads")
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notification_read"
        constraints = [models.UniqueConstraint(fields=["notification", "profile"], name="uniq_notification_read")]
