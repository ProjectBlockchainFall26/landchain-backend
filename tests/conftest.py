"""Shared fixtures. Unit tests need only Postgres + PostGIS. Tests marked `chain` also need Ganache seeded with
`npm run setup:local` in landchain-contracts; they are skipped when it isn't reachable."""
from __future__ import annotations

import time
import uuid

import jwt
import pytest

SUPABASE_URL = "https://test-ref.supabase.co"
JWT_SECRET = "test-jwt-secret-for-landchain-tests-only"


@pytest.fixture(autouse=True)
def _settings(settings):
    settings.SUPABASE_URL = SUPABASE_URL
    settings.SUPABASE_JWT_SECRET = JWT_SECRET
    settings.SUPABASE_SERVICE_ROLE_KEY = ""
    settings.DEV_AUTH = False
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                                   "LOCATION": f"t-{uuid.uuid4()}"}}
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.INDEXER_INLINE = True
    settings.CAPTCHA_SECRET = ""
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    from config.celery import app
    app.conf.task_always_eager = True
    app.conf.task_eager_propagates = True
    from django.core.cache import cache
    cache.clear()
    yield


def make_token(sub: str, *, email: str | None = None, role: str = "authenticated", exp_in: int = 3600,
               secret: str = JWT_SECRET, **extra) -> str:
    now = int(time.time())
    claims = {"sub": sub, "aud": "authenticated", "iss": f"{SUPABASE_URL}/auth/v1", "iat": now, "exp": now + exp_in,
              "role": role, "email": email, "aal": "aal1", **extra}
    return jwt.encode(claims, secret, algorithm="HS256")


@pytest.fixture
def api():
    from rest_framework.test import APIClient
    return APIClient()


class Caller:
    """An API client signed in as one Supabase user (HS256 token)."""

    def __init__(self, profile):
        from rest_framework.test import APIClient
        self.profile = profile
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {make_token(str(profile.supabase_user_id), email=profile.email)}")

    def get(self, url, **kw):
        return self.client.get(url, **kw)

    def post(self, url, data=None, **kw):
        kw.setdefault("format", "json")
        return self.client.post(url, data or {}, **kw)

    def patch(self, url, data=None, **kw):
        kw.setdefault("format", "json")
        return self.client.patch(url, data or {}, **kw)

    def delete(self, url, **kw):
        return self.client.delete(url, **kw)


@pytest.fixture
def as_user():
    def make(profile):
        return Caller(profile)
    return make


@pytest.fixture
def profile_factory(db):
    from landchain.accounts.models import Profile
    from landchain.chain.encoding import public_id

    def make(email=None, *, name="Test Person", wallet=None, roles=None, **kw):
        email = email or f"{uuid.uuid4().hex[:8]}@example.com"
        return Profile.objects.create(
            supabase_user_id=uuid.uuid4(), email=email, full_name=name, wallet_address=wallet.lower() if wallet else None,
            public_id=public_id(wallet) if wallet else None, roles=roles or [], **kw)
    return make


def chain_available() -> bool:
    try:
        from landchain.chain import client
        client.deployment()
        client.head_block()
        return client.contracts_match()
    except Exception:
        return False


@pytest.fixture
def chain(transactional_db, settings):
    """Ganache with the LandChain contracts, indexed into the test database, plus the 8 demo profiles."""
    if not chain_available():
        pytest.skip("Ganache with the LandChain contracts is not running (npm run chain + npm run setup:local)")
    from django.core.management import call_command

    from landchain.indexer.runner import run_once
    settings.CHAIN_ALLOW_UNLOCKED_SIGNING = True
    settings.DEMO_MODE = True
    call_command("seed_demo_users", verbosity=0)
    while run_once().get("skipped"):
        time.sleep(0.2)
    return True


@pytest.fixture
def demo(chain):
    from landchain.accounts.models import Profile
    people = {p.email.split("@")[0]: p for p in Profile.objects.filter(is_demo=True)}
    return {k: Caller(v) for k, v in people.items()}
