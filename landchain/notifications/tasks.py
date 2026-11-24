"""Celery tasks for `notifications` (spec section 13)."""
from celery import shared_task


@shared_task(name="notify.relay", bind=True, max_retries=3, default_retry_delay=30, retry_backoff=True)
def relay(self, notification_id: str):
    """Email / SMS relay with 3 retries and backoff. Respects notify_email / notify_sms."""
    from .models import Notification
    from .service import relay_now
    n = Notification.objects.filter(pk=notification_id).first()
    if n is None or n.relayed_at:
        return 0
    try:
        return relay_now(n)
    except Exception as e:
        raise self.retry(exc=e) from e
