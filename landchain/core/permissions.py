"""C1 (Person C): permission classes from spec section 5.5.

`request.user` is the Profile set by the auth classes (task A2), or None when anonymous
(settings: UNAUTHENTICATED_USER = None). Profile fields used (frozen in J1):
wallet_address, public_id, roles (subset of {registrar, id_officer, admin}).
"""
from rest_framework.permissions import BasePermission

OFFICER_ROLES = {"registrar", "id_officer"}


def get_roles(user) -> set:
    return set(getattr(user, "roles", None) or [])


def is_officer(user) -> bool:
    """Officer = registrar or id_officer. Admin alone is not an officer."""
    return user is not None and bool(get_roles(user) & OFFICER_ROLES)


def kind_of(user) -> str:
    """'public' | 'citizen' | 'officer', as the UI expects."""
    if user is None:
        return "public"
    return "officer" if is_officer(user) else "citizen"


def _identity_is_verified(user) -> bool:
    # ChainIdentity is the projection table built in C2; imported lazily so this module
    # loads before C2 is merged.
    from landchain.registry.models import ChainIdentity

    return ChainIdentity.objects.filter(
        address=user.wallet_address, status="verified"
    ).exists()


class Public(BasePermission):
    """Anyone, token optional. The view must filter its response with core.privacy."""

    def has_permission(self, request, view):
        return True


class IsSignedIn(BasePermission):
    def has_permission(self, request, view):
        return request.user is not None


class HasWallet(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return user is not None and bool(getattr(user, "wallet_address", None))


class IsVerifiedCitizen(BasePermission):
    """Wallet linked, not an officer, and on-chain identity status is 'verified'."""

    def has_permission(self, request, view):
        user = request.user
        if user is None or not getattr(user, "wallet_address", None):
            return False
        if is_officer(user):
            return False
        return _identity_is_verified(user)


class IsOfficer(BasePermission):
    def has_permission(self, request, view):
        return is_officer(request.user)


class IsIdentityOfficer(BasePermission):
    def has_permission(self, request, view):
        return request.user is not None and "id_officer" in get_roles(request.user)


class IsRegistrar(BasePermission):
    def has_permission(self, request, view):
        return request.user is not None and "registrar" in get_roles(request.user)


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user is not None and "admin" in get_roles(request.user)
