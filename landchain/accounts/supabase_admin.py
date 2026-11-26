"""Supabase Admin API helpers (service-role key, server only). Tasks A5 and A6.

Every function is a no-op that returns None when Supabase isn't configured (local development with X-Dev-User).
"""
from __future__ import annotations

import logging

from django.conf import settings

log = logging.getLogger("landchain.accounts")


def configured() -> bool:
    return bool(settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY)


def _admin():
    from supabase import create_client
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY).auth.admin


def _users():
    page, out = 1, []
    while True:
        batch = _admin().list_users(page=page, per_page=200)
        out += list(batch)
        if len(batch) < 200:
            return out
        page += 1


def find_user_by_email(email: str):
    if not configured():
        return None
    email = email.strip().lower()
    for u in _users():
        if (u.email or "").lower() == email:
            return u
    return None


def ensure_user(email: str, password: str, full_name: str):
    """Create (or update the password of) a confirmed email user. Returns the Supabase user."""
    if not configured():
        return None
    u = find_user_by_email(email)
    attrs = {"password": password, "email_confirm": True, "user_metadata": {"full_name": full_name}}
    if u is None:
        return _admin().create_user({"email": email, **attrs}).user
    return _admin().update_user_by_id(u.id, attrs).user


def sync_roles(user_id: str, roles: list[str]):
    """Mirror Profile.roles into app_metadata.landchain_roles so new tokens carry the hint (spec 5.6 item 8)."""
    if not configured():
        return
    try:
        _admin().update_user_by_id(str(user_id), {"app_metadata": {"landchain_roles": list(roles)}})
    except Exception:
        log.exception("Could not sync roles to Supabase for %s", user_id)
