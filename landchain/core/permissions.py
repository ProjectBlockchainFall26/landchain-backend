"""Permission classes from spec 5.5. Task C1.

A view can set `forbidden_message` to the sentence the UI shows when the role check fails
(e.g. "Only the registrar can approve a registration"), matching the contract's own wording.
"""
from __future__ import annotations

from django.conf import settings
from rest_framework import exceptions
from rest_framework.permissions import SAFE_METHODS, BasePermission


def viewer(request):
    """The caller's Profile, or None for anonymous visitors."""
    user = getattr(request, "user", None)
    return getattr(user, "profile", None)


def _deny(code: str, message: str):
    raise exceptions.PermissionDenied({"code": code, "message": message})


def _require_signed_in(request):
    if viewer(request) is None:
        raise exceptions.NotAuthenticated()
    return viewer(request)


def _check_mfa(request):
    if settings.REQUIRE_OFFICER_MFA and request.method not in SAFE_METHODS:
        if getattr(request.user, "aal", "aal1") != "aal2":
            _deny("MFA_REQUIRED", "Turn on two-step sign-in for officer actions.")


class Public(BasePermission):
    def has_permission(self, request, view):
        return True


class IsSignedIn(BasePermission):
    def has_permission(self, request, view):
        _require_signed_in(request)
        return True


class HasWallet(BasePermission):
    def has_permission(self, request, view):
        p = _require_signed_in(request)
        if not p.wallet_address:
            _deny("WALLET_REQUIRED", "Connect your wallet first.")
        return True


def chain_identity_status(profile) -> str:
    """none | pending | verified | rejected, from the indexed IdentityRegistry state."""
    if not profile or not profile.wallet_address:
        return "none"
    from landchain.registry.models import ChainIdentity
    ci = ChainIdentity.objects.filter(address=profile.wallet_address).only("status").first()
    return ci.status_name if ci else "none"


class IsVerifiedCitizen(BasePermission):
    def has_permission(self, request, view):
        p = _require_signed_in(request)
        if not p.wallet_address:
            _deny("WALLET_REQUIRED", "Connect your wallet first.")
        if p.is_officer:
            _deny("FORBIDDEN", getattr(view, "forbidden_message", None)
                  or "Lands Commission accounts act through the Review Queue.")
        if chain_identity_status(p) != "verified":
            _deny("IDENTITY_NOT_VERIFIED", getattr(view, "identity_message", None)
                  or "Verify your identity before registering land")
        return True


class _RoleRequired(BasePermission):
    role: str = ""
    default_message = "You don't have the Lands Commission role for this."

    def allowed(self, profile) -> bool:
        return self.role in (profile.roles or [])

    def has_permission(self, request, view):
        p = _require_signed_in(request)
        if not self.allowed(p):
            _deny("FORBIDDEN", getattr(view, "forbidden_message", None) or self.default_message)
        if self.role != "admin":
            _check_mfa(request)
        return True


class IsOfficer(_RoleRequired):
    default_message = "Only Lands Commission officers can see this."

    def allowed(self, profile):
        return profile.is_officer


class IsIdentityOfficer(_RoleRequired):
    role = "id_officer"
    default_message = "Only an identity officer can do this"


class IsRegistrar(_RoleRequired):
    role = "registrar"
    default_message = "Only the registrar can do this."


class IsAdmin(_RoleRequired):
    role = "admin"
    default_message = "Only a LandChain admin can do this."
