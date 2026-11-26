"""Authentication. Task A2, spec 5.3.

SupabaseJWTAuthentication verifies a Supabase access token (HS256 legacy secret or ES256/RS256 via JWKS) and
loads or creates the Profile. DevHeaderAuthentication lets a developer act as anyone locally with
`X-Dev-User: <email>`; it is active only when DEBUG and DEV_AUTH are both true.
"""
from __future__ import annotations

import logging
import uuid

import jwt
from django.conf import settings
from jwt import PyJWKClient
from rest_framework import authentication, exceptions

from .models import Profile

log = logging.getLogger(__name__)

_jwks_client: PyJWKClient | None = None


def _jwks() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(f"{settings.SUPABASE_URL}/auth/v1/.well-known/jwks.json",
                                   cache_keys=True, lifespan=600)
    return _jwks_client


class SupabaseUser:
    """request.user for DRF. is_authenticated is True; .profile is the Profile row."""

    is_authenticated = True
    is_anonymous = False

    def __init__(self, profile: Profile, claims: dict):
        self.profile, self.claims = profile, claims
        self.pk = profile.pk

    @property
    def aal(self) -> str:
        return self.claims.get("aal", "aal1")

    @property
    def session_id(self):
        return self.claims.get("session_id")

    def __str__(self):
        return str(self.profile)


def _fail(code: str, message: str):
    raise exceptions.AuthenticationFailed({"code": code, "message": message})


def decode_supabase_token(token: str) -> dict:
    try:
        alg = jwt.get_unverified_header(token).get("alg")
        if alg == "HS256":
            if not settings.SUPABASE_JWT_SECRET:
                log.warning("Rejected a Supabase token: it is HS256 and SUPABASE_JWT_SECRET is not set")
                _fail("TOKEN_INVALID", "Sign in again.")
            key = settings.SUPABASE_JWT_SECRET
        elif alg in ("ES256", "RS256", "EdDSA"):
            key = _jwks().get_signing_key_from_jwt(token).key
        else:
            log.warning("Rejected a Supabase token: unsupported algorithm %s", alg)
            _fail("TOKEN_INVALID", "Sign in again.")
        claims = jwt.decode(
            token, key, algorithms=[alg],
            audience=settings.SUPABASE_JWT_AUDIENCE,
            issuer=f"{settings.SUPABASE_URL}/auth/v1",
            leeway=60,
            options={"require": ["exp", "sub"]},
        )
    except jwt.ExpiredSignatureError:
        _fail("TOKEN_EXPIRED", "Your session expired. Sign in again.")
    except (jwt.PyJWTError, jwt.PyJWKClientError, ValueError) as e:
        # Never log the token or the secret: the algorithm and the reason are enough to fix the setup.
        log.warning("Rejected a Supabase token (%s): %s: %s", locals().get("alg"), type(e).__name__, e)
        _fail("TOKEN_INVALID", "Sign in again.")
    if claims.get("role") != "authenticated":
        log.warning("Rejected a Supabase token: role is %s, not authenticated", claims.get("role"))
        _fail("TOKEN_INVALID", "Sign in again.")
    return claims


def profile_for_claims(claims: dict) -> Profile:
    email = (claims.get("email") or None)
    email = email.lower() if email else None
    phone = claims.get("phone") or None
    profile, created = Profile.objects.get_or_create(
        supabase_user_id=claims["sub"],
        defaults={"email": email, "phone": phone,
                  "full_name": ((claims.get("user_metadata") or {}).get("full_name") or "")[:120]},
    )
    if not created and (profile.email != email or (phone and profile.phone != phone)):
        profile.email = email
        if phone:
            profile.phone = phone
        profile.save(update_fields=["email", "phone", "updated_at"])
    return profile


class SupabaseJWTAuthentication(authentication.BaseAuthentication):
    www_authenticate_realm = "api"

    def authenticate(self, request):
        header = authentication.get_authorization_header(request).decode(errors="ignore")
        if not header.lower().startswith("bearer "):
            return None  # anonymous: public endpoints still work
        token = header[7:].strip()
        if not token:
            _fail("TOKEN_INVALID", "Sign in again.")
        claims = decode_supabase_token(token)
        return SupabaseUser(profile_for_claims(claims), claims), token

    def authenticate_header(self, request):
        return 'Bearer realm="api"'


DEV_NAMESPACE = uuid.UUID("6f1a2c3e-4b5d-4e6f-8a9b-0c1d2e3f4a5b")


def dev_user_id(email: str) -> uuid.UUID:
    """Stable fake Supabase user id for local dev logins and demo users without Supabase."""
    return uuid.uuid5(DEV_NAMESPACE, email.strip().lower())


class DevHeaderAuthentication(authentication.BaseAuthentication):
    """Local only: `X-Dev-User: ama@demo.landchain.local` acts as that profile (created on first use)."""

    def authenticate(self, request):
        if not (settings.DEBUG and settings.DEV_AUTH):
            return None
        email = (request.headers.get("X-Dev-User") or "").strip().lower()
        if not email:
            return None
        profile = Profile.objects.filter(email=email).first()
        if profile is None:
            profile = Profile.objects.create(supabase_user_id=dev_user_id(email), email=email)
        claims = {"sub": str(profile.supabase_user_id), "email": email, "role": "authenticated",
                  "aal": "aal2", "dev": True}
        return SupabaseUser(profile, claims), None

    def authenticate_header(self, request):
        return 'Bearer realm="api"'
