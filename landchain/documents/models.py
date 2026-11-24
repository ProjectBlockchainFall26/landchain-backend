"""Models for `documents` (task D2). Replaces the browser's IndexedDB vault."""
from django.db import models

from landchain.core.ids import new_doc

DOC_TYPES = [
    {"type": "Site plan", "required": True, "note": "Prepared by a licensed surveyor, approved by Survey & Mapping"},
    {"type": "Indenture", "required": True, "note": "Proof of ownership: indenture, family declaration or deed of gift"},
    {"type": "Search report", "required": True, "note": "Official search from the Lands Commission"},
    {"type": "Consent / concurrence", "required": False, "note": "Only for stool or family land"},
]
DOC_TYPE_NAMES = [d["type"] for d in DOC_TYPES]
REQUIRED_DOC_TYPES = [d["type"] for d in DOC_TYPES if d["required"]]
ALLOWED_MIME = {"application/pdf", "image/jpeg", "image/png"}


class Document(models.Model):
    class Status(models.TextChoices):
        STAGED = "staged"
        ATTACHED = "attached"
        ORPHANED = "orphaned"

    id = models.CharField(max_length=40, primary_key=True, default=new_doc, editable=False)
    sha256 = models.CharField(max_length=66, db_index=True)
    doc_type = models.CharField(max_length=40)
    original_name = models.CharField(max_length=255)       # private: may contain a person's name
    mime = models.CharField(max_length=80)
    size_bytes = models.IntegerField()
    storage_path = models.CharField(max_length=300)        # <sha256>, inside the parcel-documents bucket
    uploaded_by = models.ForeignKey("accounts.Profile", on_delete=models.PROTECT, related_name="documents")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.STAGED, db_index=True)
    parcel_record_id = models.IntegerField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    attached_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "document"
        constraints = [models.UniqueConstraint(fields=["sha256", "uploaded_by"], name="uniq_doc_per_uploader")]
