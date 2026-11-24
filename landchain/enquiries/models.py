"""Models for `enquiries` (task A8). Replaces the browser's localStorage enquiries."""
from django.db import models

from landchain.core.ids import new_enq


class Enquiry(models.Model):
    class Status(models.TextChoices):
        NEW = "new"
        READ = "read"
        ANSWERED = "answered"

    id = models.CharField(max_length=40, primary_key=True, default=new_enq, editable=False)
    parcel_id = models.CharField(max_length=11, db_index=True)
    record_id = models.IntegerField()
    to_public_id = models.CharField(max_length=11, db_index=True)      # owner at the time
    to_profile = models.ForeignKey("accounts.Profile", null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="enquiries_received")  # never returned to the sender
    from_profile = models.ForeignKey("accounts.Profile", null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name="enquiries_sent")
    from_public_id = models.CharField(max_length=11, default="public")
    name = models.CharField(max_length=120)
    contact = models.CharField(max_length=160)
    message = models.TextField(max_length=2000)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.NEW, db_index=True)
    relayed_at = models.DateTimeField(null=True, blank=True)
    ip_hash = models.CharField(max_length=64, blank=True, default="", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    answered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "enquiry"
        ordering = ["-created_at"]
