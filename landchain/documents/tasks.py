"""Celery tasks for `documents` (spec section 13)."""
from celery import shared_task


@shared_task(name="documents.cleanup")
def documents_cleanup():
    """Daily: delete staged files older than 7 days that never reached a record."""
    from .service import cleanup
    return cleanup()


@shared_task(name="documents.attach")
def documents_attach(record_id: int, applicant_address: str):
    """After each ApplicationSubmitted: attach staged documents. The indexer calls the helper inline."""
    from .service import attach_for_record
    return attach_for_record(record_id, applicant_address)
