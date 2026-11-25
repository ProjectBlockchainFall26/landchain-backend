"""One test per row of the privacy table in spec section 11."""
from types import SimpleNamespace as NS
from unittest import mock

import pytest

from landchain.core import privacy as V

PARCEL = NS(owner_public_id="GH-owner001", applicant_public_id="GH-applic01",
            owner_public_ids=["GH-oldown01", "GH-owner001"])
TARGET = NS(full_name="Ama Owusu")


def u(pid=None, roles=None):
    return NS(public_id=pid, roles=roles or [], wallet_address=None)


@pytest.mark.parametrize("viewer,expected", [
    (None, False),
    (u("GH-stranger"), False),
    (u(None), False),
    (u("GH-owner001"), True),
    (u("GH-oldown01"), True),
    (u("GH-applic01"), True),
    (u(roles=["registrar"]), True),
    (u(roles=["id_officer"]), True),
    (u(roles=["admin"]), False),
])
def test_can_see_private(viewer, expected):
    assert V.can_see_private(viewer, PARCEL) is expected


def test_can_see_private_from_owner_history_rows():
    parcel = NS(owner_public_id="GH-a", applicant_public_id="GH-b",
                owner_history=[NS(public_id="GH-past0001")])
    assert V.can_see_private(u("GH-past0001"), parcel)
    assert not V.can_see_private(u("GH-nobody01"), parcel)


def names(viewer, role_label=None, target=TARGET):
    with mock.patch.object(V, "role_label_for", return_value=role_label), \
         mock.patch.object(V, "_profile_by_public_id", return_value=target):
        return V.shown_name(viewer, "GH-7d4e894d")


def test_name_hidden_from_public_and_strangers():
    assert names(None) is None
    assert names(u("GH-stranger")) is None


def test_name_visible_to_officers_and_self():
    assert names(u(roles=["registrar"])) == "Ama Owusu"
    assert names(u("GH-7d4e894d")) == "Ama Owusu"


def test_officer_wallet_role_name_always_shown():
    assert names(None, role_label="Lands Commission registrar") == "Lands Commission registrar"


def test_unknown_person_is_none():
    assert names(u(roles=["registrar"]), target=None) is None


def test_person_ref_citizen_public_falls_back_to_public_id():
    with mock.patch.object(V, "role_label_for", return_value=None), \
         mock.patch.object(V, "_profile_by_public_id", return_value=TARGET):
        ref = V.person_ref(None, "GH-7d4e894d")
    assert ref == {"public_id": "GH-7d4e894d", "name": None, "kind": "citizen", "label": "GH-7d4e894d"}


def test_person_ref_citizen_for_officer_shows_name():
    with mock.patch.object(V, "role_label_for", return_value=None), \
         mock.patch.object(V, "_profile_by_public_id", return_value=TARGET):
        ref = V.person_ref(u(roles=["registrar"]), "GH-7d4e894d")
    assert ref["name"] == "Ama Owusu" and ref["label"] == "Ama Owusu"


def test_person_ref_officer_wallet():
    with mock.patch.object(V, "role_label_for", return_value="Lands Commission registrar"):
        ref = V.person_ref(None, "GH-1a2b3c4d")
    assert ref == {"public_id": "GH-1a2b3c4d", "name": "Lands Commission registrar",
                   "kind": "officer", "label": "Lands Commission registrar"}


def test_person_ref_serializer_uses_request_user():
    with mock.patch.object(V, "role_label_for", return_value=None), \
         mock.patch.object(V, "_profile_by_public_id", return_value=TARGET):
        data = V.PersonRefSerializer("GH-7d4e894d", context={"request": NS(user=None)}).data
    assert data["label"] == "GH-7d4e894d"


def test_public_id_of_matches_format():
    pytest.importorskip("eth_utils")
    pid = V.public_id_of("0x28a8746e75304c0780e011bed21c72cd78cd535e")
    assert pid.startswith("GH-") and len(pid) == 11
