"""Document helpers other apps call (task D2). attach_for_record is called by the indexer (task C8, job 13.4)."""
from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from . import storage
from .models import Document


def attach_for_record(record_id: int, applicant_address: str) -> int:
    """Mark the applicant's staged documents whose fingerprints are on the record as attached."""
    from landchain.registry.models import ParcelDoc
    hashes = list(ParcelDoc.objects.filter(parcel_id=record_id).values_list("sha256", flat=True))
    if not hashes:
        return 0
    return Document.objects.filter(
        uploaded_by__wallet_address=applicant_address.lower(), sha256__in=hashes,
        status__in=[Document.Status.STAGED, Document.Status.ORPHANED],
    ).update(status=Document.Status.ATTACHED, parcel_record_id=record_id, attached_at=timezone.now())


def file_for(sha256: str, record_id: int | None = None) -> Document | None:
    """The stored file for a fingerprint: prefer the copy attached to this record, else any copy."""
    qs = Document.objects.filter(sha256=sha256.lower())
    return (qs.filter(parcel_record_id=record_id).first() if record_id else None) or qs.order_by("created_at").first()


def available_hashes(hashes) -> set[str]:
    return set(Document.objects.filter(sha256__in=list(hashes)).values_list("sha256", flat=True))


def cleanup(days: int = 7) -> int:
    """Delete staged files older than `days` that never reached a record; never delete attached files."""
    cutoff = timezone.now() - timedelta(days=days)
    n = 0
    for doc in Document.objects.filter(status=Document.Status.STAGED, created_at__lt=cutoff):
        others = Document.objects.filter(sha256=doc.sha256).exclude(pk=doc.pk)
        if not others.exists():
            storage.delete(doc.storage_path)
        doc.delete()
        n += 1
    return n
