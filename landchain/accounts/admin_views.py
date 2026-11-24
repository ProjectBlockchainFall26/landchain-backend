"""Officer management (task A5, spec 9.13). Off chain only: officers act through the shared role wallets."""
from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from landchain.chain.service import signer_address
from landchain.core.errors import ApiError, Conflict, NotFound, Validation
from landchain.core.permissions import IsAdmin

from . import supabase_admin
from .models import ALL_ROLES, Profile
from .serializers import officer_row


def _signers() -> dict:
    out = {}
    for role in ("registrar", "id_officer", "admin"):
        try:
            out[role] = signer_address(role)
        except ApiError:
            out[role] = None
    return out


class AdminOfficersView(APIView):
    """GET / POST /api/v1/admin/officers [IsAdmin]."""

    permission_classes = [IsAdmin]

    def get(self, request, *args, **kwargs):
        rows = Profile.objects.exclude(roles=[]).order_by("full_name", "email")
        return Response({"results": [officer_row(p) for p in rows], "signers": _signers()})

    def post(self, request, *args, **kwargs):
        roles = request.data.get("roles") or []
        if not isinstance(roles, list) or not roles or any(r not in ALL_ROLES for r in roles):
            raise Validation("Pick roles from registrar, id_officer, admin",
                             field_errors={"roles": ["Pick roles from registrar, id_officer, admin"]})
        email, user_id = (request.data.get("email") or "").strip().lower(), request.data.get("user_id")
        profile = None
        if user_id:
            profile = Profile.objects.filter(supabase_user_id=user_id).first()
        elif email:
            profile = Profile.objects.filter(email=email).first()
            if profile is None:
                u = supabase_admin.find_user_by_email(email)
                if u is not None:
                    profile = Profile.objects.create(supabase_user_id=u.id, email=email,
                                                     full_name=(u.user_metadata or {}).get("full_name", "")[:120])
        else:
            raise Validation("Give an email or user_id", field_errors={"email": ["Give an email or user_id"]})
        if profile is None:
            raise NotFound("No user with that email. Ask them to sign up first.")
        from landchain.registry.selectors import parcels_owned_by
        if profile.wallet_address and profile.public_id and parcels_owned_by(profile.public_id).exists() \
                and any(r in ("registrar", "id_officer") for r in roles):
            raise Conflict("This person has a citizen wallet that holds titles, so they can't be an officer.",
                           code="OFFICER_HAS_WALLET")
        profile.roles = sorted(set(profile.roles or []) | set(roles))
        profile.save(update_fields=["roles", "updated_at"])
        supabase_admin.sync_roles(profile.supabase_user_id, profile.roles)
        return Response(officer_row(profile))


class AdminOfficersDetailView(APIView):
    """DELETE /api/v1/admin/officers/{user_id} [IsAdmin]. ?role=registrar removes one role."""

    permission_classes = [IsAdmin]

    def delete(self, request, user_id, *args, **kwargs):
        profile = get_object_or_404(Profile, supabase_user_id=user_id)
        role = request.query_params.get("role")
        if role and role not in ALL_ROLES:
            raise Validation("Unknown role", field_errors={"role": ["Use registrar, id_officer or admin"]})
        profile.roles = [r for r in profile.roles if role and r != role]
        profile.save(update_fields=["roles", "updated_at"])
        supabase_admin.sync_roles(profile.supabase_user_id, profile.roles)
        return Response(status=204)
