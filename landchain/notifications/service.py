"""notify(...) helper (task A7). The indexer (C8) and enquiries (A8) call it; nothing else creates notifications.

    notify(kind, text, recipient_public_id=None | recipient_role=None, parcel_id=None, link=None, at=None,
           source_event=None, relay=False, relay_extra=None, dedupe_key=None) -> Notification

relay=True queues notify.relay, which emails / texts the recipient (respecting notify_email / notify_sms).
Role notifications ("role:Registrar") are relayed as one message per officer.
"""
from __future__ import annotations

import logging

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from .models import Notification, NotificationRead

log = logging.getLogger("landchain.notifications")


def notify(*, kind: str, text: str, recipient_public_id: str | None = None, recipient_role: str | None = None,
           parcel_id: str | None = None, link: str | None = None, at=None, source_event=None, relay: bool = False,
           relay_extra: str | None = None, dedupe_key: str | None = None, recipient_profile=None) -> Notification:
    from landchain.accounts.models import Profile
    if recipient_profile is None and recipient_public_id:
        recipient_profile = Profile.objects.filter(public_id=recipient_public_id).first()
    if dedupe_key:
        existing = Notification.objects.filter(dedupe_key=dedupe_key).first()
        if existing:
            return existing
    try:
        with transaction.atomic():
            n = Notification.objects.create(
                kind=kind, text=text[:300], recipient_public_id=recipient_public_id, recipient_role=recipient_role,
                recipient_profile=recipient_profile, parcel_id=parcel_id, link=link, at=at or timezone.now(),
                source_event=source_event, relay=relay, relay_extra=relay_extra, dedupe_key=dedupe_key)
    except IntegrityError:
        return Notification.objects.get(dedupe_key=dedupe_key)
    if relay:
        from .tasks import relay as relay_task
        transaction.on_commit(lambda: relay_task.delay(n.id))
    return n


def audience_q(profile) -> Q:
    """Notifications addressed to this person or to one of their roles."""
    q = Q(recipient_profile=profile)
    if profile.public_id:
        q |= Q(recipient_public_id=profile.public_id)
    roles = [r for r in (profile.roles or []) if r in ("registrar", "id_officer")]
    if roles:
        q |= Q(recipient_role__in=roles)
    return q


def for_profile(profile):
    return Notification.objects.filter(audience_q(profile))


def unread_for(profile):
    return for_profile(profile).exclude(reads__profile=profile)


def mark_read(profile, ids: list[str] | None = None, all_: bool = False) -> int:
    qs = unread_for(profile)
    if not all_:
        qs = qs.filter(id__in=ids or [])
    rows = [NotificationRead(notification=n, profile=profile) for n in qs]
    NotificationRead.objects.bulk_create(rows, ignore_conflicts=True)
    return len(rows)


# ---------------------------------------------------------------- relay
def recipients(n: Notification):
    from landchain.accounts.models import Profile
    if n.recipient_role:
        return list(Profile.objects.filter(roles__contains=[n.recipient_role]))
    if n.recipient_profile_id:
        return [n.recipient_profile]
    if n.recipient_public_id:
        return list(Profile.objects.filter(public_id=n.recipient_public_id))
    return []


def send_sms(to: str, body: str) -> bool:
    from django.conf import settings
    provider = (settings.SMS_PROVIDER or "").lower()
    if not provider:
        log.info("SMS (not sent, no SMS_PROVIDER) to %s: %s", to, body)
        return False
    import requests
    if provider == "twilio":
        sid, _, token = settings.SMS_API_KEY.partition(":")
        r = requests.post(f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json", auth=(sid, token),
                          data={"From": settings.SMS_SENDER_ID, "To": to, "Body": body}, timeout=15)
    elif provider == "hubtel":
        cid, _, secret = settings.SMS_API_KEY.partition(":")
        r = requests.get("https://smsc.hubtel.com/v1/messages/send", timeout=15, params={
            "clientid": cid, "clientsecret": secret, "from": settings.SMS_SENDER_ID, "to": to, "content": body})
    else:
        raise ValueError(f"Unknown SMS_PROVIDER {provider}")
    r.raise_for_status()
    return True


def relay_now(n: Notification) -> int:
    """Send the email / SMS for one notification. Returns the number of messages sent."""
    from django.conf import settings
    from django.core.mail import send_mail
    sent = 0
    body = n.text + (f"\n\n{n.relay_extra}" if n.relay_extra else "")
    link = f"{settings.SITE_URI}{n.link}" if n.link else settings.SITE_URI
    for p in recipients(n):
        if p.notify_email and p.email:
            send_mail(f"LandChain: {n.text[:70]}", f"{body}\n\n{link}", settings.DEFAULT_FROM_EMAIL, [p.email])
            sent += 1
        if p.notify_sms and p.phone:
            if send_sms(p.phone, f"LandChain: {body}"[:459]):
                sent += 1
    n.relayed_at = timezone.now()
    n.save(update_fields=["relayed_at"])
    return sent
