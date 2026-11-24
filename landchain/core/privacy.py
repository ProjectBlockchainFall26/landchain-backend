"""Privacy rules, the server-side port of the frontend's privacy.ts (spec sections 8 and 11). Task C1.

Every serializer asks these functions; no other file decides who may see a name, document, fee or contact.
"""
from __future__ import annotations

from django.db.models import Q

ROLE_WALLET_LABEL = {"registrar": "Lands Commission registrar", "id_officer": "Lands Commission identity officer",
                     "admin": "Lands Commission admin"}


class PeopleIndex:
    """Caches the lookups PersonRef needs for one request (profiles by public ID, role wallets)."""

    def __init__(self):
        self._profiles: dict[str, object] = {}
        self._roles: dict[str, list[str]] | None = None

    def roles_by_public_id(self) -> dict[str, list[str]]:
        if self._roles is None:
            from landchain.chain.encoding import public_id
            from landchain.registry.models import ChainRole
            out: dict[str, list[str]] = {}
            for r in ChainRole.objects.all():
                out.setdefault(public_id(r.address), []).append(r.role)
            self._roles = out
        return self._roles

    def profile(self, pid: str):
        if pid not in self._profiles:
            from landchain.accounts.models import Profile
            self._profiles[pid] = Profile.objects.filter(public_id=pid).first()
        return self._profiles[pid]

    def prefetch(self, pids):
        from landchain.accounts.models import Profile
        missing = [p for p in set(pids) if p and p not in self._profiles]
        if missing:
            found = {p.public_id: p for p in Profile.objects.filter(public_id__in=missing)}
            for p in missing:
                self._profiles[p] = found.get(p)


def is_officer(viewer) -> bool:
    return bool(viewer and viewer.is_officer)


def can_see_private(viewer, parcel) -> bool:
    """Officers and the parcel's own owner, applicant or past owners see its private details."""
    if viewer is None:
        return False
    if viewer.is_officer:
        return True
    pid = viewer.public_id
    if not pid:
        return False
    return (pid == parcel.owner_public_id or pid == parcel.applicant_public_id
            or parcel.owners.filter(public_id=pid).exists())


def private_parcel_q(viewer) -> Q | None:
    """Queryset filter for parcels whose private details the viewer may see (None = all of them)."""
    if viewer is not None and viewer.is_officer:
        return None
    pid = getattr(viewer, "public_id", None)
    if not pid:
        return Q(pk__in=[])
    return Q(owner_public_id=pid) | Q(applicant_public_id=pid) | Q(owners__public_id=pid)


def shown_name(viewer, person_public_id: str | None, people: PeopleIndex | None = None) -> str | None:
    """Officers' names always (they act officially); everyone else's only to officers and themselves."""
    if not person_public_id:
        return None
    people = people or PeopleIndex()
    roles = people.roles_by_public_id().get(person_public_id)
    target = people.profile(person_public_id)
    if roles:
        return (target.full_name if target and target.full_name else None) or "Lands Commission"
    if target is None:
        return None
    if viewer and (viewer.is_officer or viewer.public_id == person_public_id):
        return target.full_name or None
    return None


def person_ref(viewer, person_public_id: str | None, people: PeopleIndex | None = None) -> dict | None:
    """PersonRef (spec 8): {public_id, name, kind, label}."""
    if not person_public_id:
        return None
    people = people or PeopleIndex()
    roles = people.roles_by_public_id().get(person_public_id)
    name = shown_name(viewer, person_public_id, people)
    if roles:
        role = "registrar" if "registrar" in roles else ("id_officer" if "id_officer" in roles else roles[0])
        return {"public_id": person_public_id, "name": name, "kind": "officer", "label": ROLE_WALLET_LABEL[role]}
    target = people.profile(person_public_id)
    kind = "officer" if (target and target.is_officer) else "citizen"
    return {"public_id": person_public_id, "name": name, "kind": kind, "label": name or person_public_id}


def person_ref_for_address(viewer, address: str | None, people: PeopleIndex | None = None) -> dict | None:
    if not address:
        return None
    from landchain.chain.encoding import ZERO_ADDRESS, public_id
    if address.lower() == ZERO_ADDRESS:
        return None
    return person_ref(viewer, public_id(address), people)


def can_see_contact(viewer, profile) -> bool:
    """Email, phone and card hash: the person themself and officers (identity queue)."""
    return bool(viewer and (viewer.is_officer or viewer.pk == profile.pk))


def can_see_receipt_numbers(viewer) -> bool:
    """Plain receipt numbers and consideration: officers only."""
    return is_officer(viewer)


def can_read_enquiry(viewer, enquiry) -> bool:
    """Only the owner it was sent to (not even officers, decision 18.5)."""
    return bool(viewer and viewer.public_id and viewer.public_id == enquiry.to_public_id)


def can_see_officer_actions(viewer) -> bool:
    return is_officer(viewer)
