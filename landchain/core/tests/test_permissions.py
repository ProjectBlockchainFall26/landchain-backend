from types import SimpleNamespace as NS
from unittest import mock

import pytest

from landchain.core import permissions as P


def req(user):
    return NS(user=user)


def user(**kw):
    base = dict(wallet_address=None, public_id=None, roles=[])
    base.update(kw)
    return NS(**base)


WALLET = "0x28a8746e75304c0780e011bed21c72cd78cd535e"
ANON = None
NO_WALLET = user()
CITIZEN = user(wallet_address=WALLET, public_id="GH-3c1f9a02")
REGISTRAR = user(roles=["registrar"])
ID_OFFICER = user(roles=["id_officer"])
ADMIN = user(roles=["admin"])


@pytest.mark.parametrize("u", [ANON, NO_WALLET, CITIZEN, REGISTRAR])
def test_public(u):
    assert P.Public().has_permission(req(u), None) is True


@pytest.mark.parametrize("u,expected", [
    (ANON, False), (NO_WALLET, True), (CITIZEN, True), (REGISTRAR, True)])
def test_is_signed_in(u, expected):
    assert P.IsSignedIn().has_permission(req(u), None) is expected


@pytest.mark.parametrize("u,expected", [
    (ANON, False), (NO_WALLET, False), (CITIZEN, True)])
def test_has_wallet(u, expected):
    assert P.HasWallet().has_permission(req(u), None) is expected


@pytest.mark.parametrize("u,expected", [
    (ANON, False), (NO_WALLET, False), (REGISTRAR, True), (ID_OFFICER, True),
    (ADMIN, False), (CITIZEN, False)])
def test_is_officer(u, expected):
    assert P.IsOfficer().has_permission(req(u), None) is expected


def test_is_identity_officer():
    assert P.IsIdentityOfficer().has_permission(req(ID_OFFICER), None)
    assert not P.IsIdentityOfficer().has_permission(req(REGISTRAR), None)
    assert not P.IsIdentityOfficer().has_permission(req(ANON), None)


def test_is_registrar():
    assert P.IsRegistrar().has_permission(req(REGISTRAR), None)
    assert not P.IsRegistrar().has_permission(req(ID_OFFICER), None)
    assert not P.IsRegistrar().has_permission(req(ANON), None)


def test_is_admin():
    assert P.IsAdmin().has_permission(req(ADMIN), None)
    assert not P.IsAdmin().has_permission(req(REGISTRAR), None)
    assert not P.IsAdmin().has_permission(req(ANON), None)


def test_verified_citizen_needs_verified_identity():
    with mock.patch.object(P, "_identity_is_verified", return_value=True):
        assert P.IsVerifiedCitizen().has_permission(req(CITIZEN), None)
        assert not P.IsVerifiedCitizen().has_permission(req(NO_WALLET), None)
        assert not P.IsVerifiedCitizen().has_permission(req(ANON), None)
        officer_with_wallet = user(wallet_address=WALLET, roles=["registrar"])
        assert not P.IsVerifiedCitizen().has_permission(req(officer_with_wallet), None)
    with mock.patch.object(P, "_identity_is_verified", return_value=False):
        assert not P.IsVerifiedCitizen().has_permission(req(CITIZEN), None)


def test_kind_of():
    assert P.kind_of(None) == "public"
    assert P.kind_of(CITIZEN) == "citizen"
    assert P.kind_of(REGISTRAR) == "officer"
    assert P.kind_of(ADMIN) == "citizen"
