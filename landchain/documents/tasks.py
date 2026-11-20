"""Celery tasks for `documents` (spec section 13). Celery itself is wired up in B1."""

# TODO(D2, Person D): task 'documents.cleanup': Daily: delete staged files older than 7 days that never reached a record.
# TODO(C8, Person C): task 'documents.attach': After each ApplicationSubmitted: attach staged documents (C8 calls it).
