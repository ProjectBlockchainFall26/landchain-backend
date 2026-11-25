"""C1 (Person C): server-side privacy rules, port of privacy.ts (spec sections 8 and 11).

Every serializer that returns a person's name or a parcel's private fields goes through here.
Signatures were agreed in J1: can_see_private(viewer, parcel), shown_name(viewer, public_id).

`viewer` is the Profile from request.user, or None for anonymous callers.
`parcel` is anything with owner_public_id, applicant_public_id and owner_public_ids
(the Parcel projection, or a wrapper built by the serializer).
"""
from rest_framework import serializers

from landchain.core.permissions import is_officer

ROLE_LABELS = {
    "registrar": "Lands Commission registrar",
    "id_officer": "Lands Commission identity officer",
    "admin": "Lands Commission administrator",
}
# If a wallet holds several roles, show the most specific official role first.
ROLE_PRIORITY = ("registrar", "id_officer", "admin")


def public_id_of(address: str) -> str:
    """'GH-' + first 4 bytes of keccak256(address), same as IdentityRegistry.publicIdOf."""
    from eth_utils import keccak

    raw = bytes.fromhex(address.lower().removeprefix("0x"))
    return "GH-" + keccak(raw)[:4].hex()


def _owner_public_ids(parcel) -> list:
    ids = getattr(parcel, "owner_public_ids", None)
    if ids is not None:
        return list(ids)
    history = getattr(parcel, "owner_history", None)
    if history is not None:
        rows = history.all() if hasattr(history, "all") else history
        return [row.public_id for row in rows]
    return []


def can_see_private(viewer, parcel) -> bool:
    """Officers, and the parcel's own owner, applicant or past owners, see its private details."""
    if viewer is None:
        return False
    if is_officer(viewer):
        return True
    pid = getattr(viewer, "public_id", None)
    if not pid:
        return False
    return (
        pid == getattr(parcel, "owner_public_id", None)
        or pid == getattr(parcel, "applicant_public_id", None)
        or pid in _owner_public_ids(parcel)
    )


def _role_wallet_role(public_id: str):
    """If this public ID belongs to a Lands Commission role wallet, return its role."""
    from landchain.registry.models import ChainRole  # projection table from C2

    roles = {r.role for r in ChainRole.objects.all() if public_id_of(r.address) == public_id}
    return next((r for r in ROLE_PRIORITY if r in roles), None)


def _profile_by_public_id(public_id: str):
    from landchain.accounts.models import Profile  # built by A2

    return Profile.objects.filter(public_id=public_id).first()


def role_label_for(public_id: str):
    """'Lands Commission registrar' etc. for a role wallet, else None."""
    role = _role_wallet_role(public_id)
    return ROLE_LABELS[role] if role else None


def shown_name(viewer, public_id: str):
    """Role wallets: their role name, always. Everyone else: real name only for officers and
    the person themselves. Returns None when the name must stay hidden."""
    if not public_id:
        return None
    label = role_label_for(public_id)
    if label:
        return label
    target = _profile_by_public_id(public_id)
    if target is None:
        return None
    if viewer is not None and (is_officer(viewer) or getattr(viewer, "public_id", None) == public_id):
        return target.full_name or None
    return None


def person_ref(viewer, public_id: str):
    """PersonRef object (spec section 8)."""
    if not public_id:
        return None
    label = role_label_for(public_id)
    if label:
        return {"public_id": public_id, "name": label, "kind": "officer", "label": label}
    name = shown_name(viewer, public_id)
    return {"public_id": public_id, "name": name, "kind": "citizen", "label": name or public_id}


class PersonRefSerializer(serializers.Serializer):
    """Serializes a public ID string into a PersonRef. Pass `request` in the context:
    PersonRefSerializer(parcel.owner_public_id, context={"request": request}).data"""

    def to_representation(self, public_id):
        request = self.context.get("request")
        viewer = getattr(request, "user", None) if request else None
        return person_ref(viewer, public_id)
