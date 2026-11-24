"""Celery tasks for `enquiries`. The relay reuses notify.relay: an enquiry creates a relayed notification for the
owner that carries the message and the enquirer's contact (spec 9.11, job 13.3)."""
