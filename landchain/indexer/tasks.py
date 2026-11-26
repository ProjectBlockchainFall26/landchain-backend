"""Celery tasks for `indexer` (spec section 13)."""
import logging

from celery import shared_task

log = logging.getLogger("landchain.indexer")


@shared_task(name="indexer.tick", ignore_result=True)
def indexer_tick():
    """Beat task: one indexer pass (single instance through a Postgres advisory lock)."""
    from landchain.core.errors import ChainUnavailable

    from .runner import run_once
    try:
        return run_once()
    except ChainUnavailable as e:
        log.warning("Indexer: %s", e.message)
        return {"error": e.message}


@shared_task(name="indexer.resync")
def indexer_resync(from_block=None):
    from .runner import resync, run_once
    out = resync(from_block)
    run_once()
    return out
