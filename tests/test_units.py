"""Unit tests that need no chain: encoding (spec 6.4), geometry, fees, errors, ids, auth, privacy, idempotency."""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from tests.conftest import Caller, make_token

AMA = "0x22d491bde2303f2f43325b2108d26f1eaba1e32b"


# ---------------------------------------------------------------- encoding (B2)
def test_public_id_matches_contract_rule():
    from landchain.chain.encoding import public_id
    assert public_id(AMA) == "GH-9f225659"          # IdentityRegistry.publicIdOf for Ganache account 2
    assert public_id(AMA.upper().replace("0X", "0x")) == "GH-9f225659"


def test_card_and_receipt_hashes():
    from web3 import Web3

    from landchain.chain.encoding import card_hash, receipt_hash
    want = "0x" + Web3.keccak(text="landchain-card:GHA-700000006-6").hex().removeprefix("0x")
    assert card_hash(" gha-700000006-6 ") == want
    assert card_hash("GHA - 700000006 - 6") == want
    assert receipt_hash(" gra-sd-1 ") == receipt_hash("GRA-SD-1")


def test_money_and_micro_degrees():
    from landchain.chain.encoding import cedi, ghs_str, pesewas, to_micro
    assert pesewas("1178") == 117800 and pesewas(Decimal("0.005")) == 1
    assert ghs_str(74400) == "744.00" and cedi(824600) == "GH¢ 8,246.00"
    assert to_micro(5.750912) == 5750912 and to_micro(-0.228113) == -228113


# ---------------------------------------------------------------- geometry (C6)
def test_area_matches_frontend_formula():
    from landchain.registry import geo
    sq = [[5.75, -0.23], [5.75, -0.229], [5.749, -0.229], [5.749, -0.23]]
    m_lng = 111320 * __import__("math").cos(5.7505 * __import__("math").pi / 180)
    want = (0.001 * 110540) * (0.001 * m_lng) / 4046.8564
    assert abs(geo.area_acres(sq) - want) < 1e-9
    assert geo.acres_x100(sq) == round(want * 100)
    assert geo.inside_ghana(5.75, -0.23) and not geo.inside_ghana(12.0, -0.23)


@pytest.mark.django_db
def test_boundary_check_rules():
    from landchain.registry import geo
    assert geo.check_boundary([[5.75, -0.23], [5.751, -0.23]])["error"] == "A boundary needs at least 3 corner pillars"
    assert geo.check_boundary([[13.0, -0.23], [13.0, -0.22], [12.9, -0.22]])["error"] == \
        "All pillars must be inside Ghana"
    ok = geo.check_boundary([[5.75, -0.23], [5.75, -0.229], [5.749, -0.229]])
    assert ok["ok"] and ok["overlaps"] is None and ok["pillar_count"] == 3


@pytest.mark.django_db
def test_overlap_and_touching_edges(db):
    from django.contrib.gis.geos import Polygon

    from landchain.registry import geo
    from landchain.registry.models import Parcel
    Parcel.objects.create(record_id=1, parcel_id="GA-BRK-0001", status=1, owner_address=AMA,
                          owner_public_id="GH-9f225659", lats_micro=[5750000, 5750000, 5749000, 5749000],
                          lngs_micro=[-230000, -229000, -229000, -230000],
                          boundary=Polygon(((-0.23, 5.75), (-0.229, 5.75), (-0.229, 5.749), (-0.23, 5.749),
                                            (-0.23, 5.75)), srid=4326))
    overlap = [[5.7495, -0.2295], [5.7495, -0.2285], [5.7485, -0.2285], [5.7485, -0.2295]]
    touching = [[5.75, -0.229], [5.75, -0.228], [5.749, -0.228], [5.749, -0.229]]
    assert geo.check_boundary(overlap)["overlaps"] == "GA-BRK-0001"
    assert geo.check_boundary(overlap, "GA-BRK-0001")["overlaps"] is None
    assert geo.check_boundary(touching)["ok"]
    same = [[5.75, -0.23], [5.75, -0.229], [5.749, -0.229], [5.749, -0.23]]
    assert geo.check_boundary(same)["error"] == "This boundary is already registered"


# ---------------------------------------------------------------- fees (D3)
def test_fee_estimates():
    from landchain.fees.schedule import estimate, stamp_duty
    assert stamp_duty(Decimal(10000)) == 25 and stamp_duty(Decimal(20000)) == 100 and stamp_duty(Decimal(60000)) == 600
    assert estimate("First registration", 1.24)["suggested_ghs"] == "2356.00"
    assert estimate("Transfer", 0.4)["suggested_ghs"] == "973.00"
    assert estimate("Official search")["suggested_pesewas"] == 16300
    assert estimate("Stamp duty", 1, None)["suggested_ghs"] is None


@pytest.mark.django_db
def test_fee_endpoints(api):
    r = api.get("/api/v1/fees/schedule")
    assert r.status_code == 200 and [k["kind"] for k in r.json()["kinds"]] == \
        ["Official search", "Stamp duty", "First registration", "Transfer"]
    r = api.get("/api/v1/fees/estimate", {"kind": "Stamp duty", "acres": "1.24", "consideration": "60000"})
    assert r.json() == {"kind": "Stamp duty", "suggested_ghs": "600.00", "suggested_pesewas": 60000,
                        "basis": "1% of GH¢ 60,000.00"}
    assert api.get("/api/v1/fees/estimate", {"kind": "Bribe"}).json()["error"]["code"] == "VALIDATION"


# ---------------------------------------------------------------- errors and ids (B1)
def test_revert_mapping():
    from landchain.core.errors import ChainRevert
    assert ChainRevert("Only the owner can transfer this title").status_code == 422
    e = ChainRevert("Verify your identity before registering land")
    assert (e.status_code, e.code) == (403, "IDENTITY_NOT_VERIFIED")
    assert ChainRevert("Application not found").status_code == 404
    assert ChainRevert("Only the registrar can approve a registration").code == "FORBIDDEN"


def test_revert_reason_extraction():
    from web3.exceptions import Web3RPCError

    from landchain.chain.simulate import revert_reason
    e = Web3RPCError("{'message': 'VM Exception while processing transaction: revert This receipt has already been "
                     "recorded', 'code': -32000}")
    assert revert_reason(e) == "This receipt has already been recorded"
    assert revert_reason(Exception("execution reverted: Only the owner can transfer this title")) == \
        "Only the owner can transfer this title"
    assert revert_reason(Exception("MetaMask: User denied transaction signature")) == \
        "You cancelled the transaction in your wallet"


def test_ids():
    from landchain.core.errors import NotFound
    from landchain.core.ids import new_id, parse_id
    assert parse_id("APP-7", "APP") == 7 and parse_id("7", "APP") == 7 and parse_id("trf-3", "TRF") == 3
    with pytest.raises(NotFound):
        parse_id("APP-x", "APP")
    assert new_id("txi").startswith("txi_") and len(new_id("txi")) == 30


@pytest.mark.django_db
def test_health_and_error_shape(api):
    r = api.get("/api/v1/health")
    assert r.status_code == 200 and r.json()["db"] == "ok"
    r = api.get("/api/v1/me")
    body = r.json()["error"]
    assert r.status_code == 401 and body["code"] == "AUTH_REQUIRED" and body["request_id"].startswith("req_")
    assert set(body) == {"code", "message", "revert_reason", "field_errors", "request_id"}


# ---------------------------------------------------------------- auth (A2) — spec 17 test 9
@pytest.mark.django_db
def test_jwt_hs256_expired_and_anon(api):
    sub = str(uuid.uuid4())
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {make_token(sub, email='New@Example.com', user_metadata={'full_name': 'Efua M'})}")
    r = api.get("/api/v1/me")
    assert r.status_code == 200 and r.json()["email"] == "new@example.com" and r.json()["full_name"] == "Efua M"
    assert r.json()["kind"] == "citizen" and r.json()["roles"] == ["Citizen"]
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {make_token(sub, exp_in=-120)}")
    r = api.get("/api/v1/me")
    assert r.status_code == 401 and r.json()["error"]["code"] == "TOKEN_EXPIRED"
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {make_token(sub, role='anon')}")
    assert api.get("/api/v1/me").json()["error"]["code"] == "TOKEN_INVALID"
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {make_token(sub, secret='wrong')}")
    assert api.get("/api/v1/me").json()["error"]["code"] == "TOKEN_INVALID"


@pytest.mark.django_db
def test_jwt_jwks_es256(api, monkeypatch):
    import jwt as pyjwt
    from cryptography.hazmat.primitives.asymmetric import ec

    from landchain.accounts import auth
    from tests.conftest import SUPABASE_URL
    key = ec.generate_private_key(ec.SECP256R1())

    class FakeJWKS:
        def get_signing_key_from_jwt(self, token):
            return type("K", (), {"key": key.public_key()})()
    monkeypatch.setattr(auth, "_jwks", lambda: FakeJWKS())
    import time
    now = int(time.time())
    tok = pyjwt.encode({"sub": str(uuid.uuid4()), "aud": "authenticated", "iss": f"{SUPABASE_URL}/auth/v1",
                        "iat": now, "exp": now + 60, "role": "authenticated", "email": "es@example.com"},
                       key, algorithm="ES256", headers={"kid": "k1"})
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {tok}")
    assert api.get("/api/v1/me").status_code == 200


@pytest.mark.django_db
def test_patch_me_validation(profile_factory):
    c = Caller(profile_factory(name="Ama"))
    assert c.patch("/api/v1/me", {"full_name": "A"}).json()["error"]["field_errors"]["full_name"]
    assert c.patch("/api/v1/me", {"phone": "+23324"}).status_code == 400
    r = c.patch("/api/v1/me", {"full_name": "Ama Owusu", "phone": "+233240000000", "notify": {"sms": True}})
    assert r.status_code == 200 and r.json()["phone"] == "+233240000000" and r.json()["notify"]["sms"] is True


# ---------------------------------------------------------------- permissions and privacy (C1)
@pytest.fixture
def parcel(db):
    from landchain.registry.models import OwnerHistory, Parcel
    yaw, kofi = "0xe11ba2b4d45eaed5996cd0823791e0c93114882d", "0xd03ea8624c8c5987235048901fb614fdca89b117"
    p = Parcel.objects.create(record_id=1, parcel_id="GA-BRK-0001", status=1, owner_address=kofi,
                              owner_public_id="GH-a6e02fa9", applicant_address=yaw, applicant_public_id="GH-d6604a25",
                              token_id=1, lats_micro=[5750000, 5750000, 5749000],
                              lngs_micro=[-230000, -229000, -229000], acres_x100=124)
    OwnerHistory.objects.create(parcel=p, position=0, address=yaw, public_id="GH-d6604a25")
    OwnerHistory.objects.create(parcel=p, position=1, address=kofi, public_id="GH-a6e02fa9")
    return p


@pytest.mark.django_db
def test_privacy_rules(parcel, profile_factory, api):
    from landchain.core import privacy
    yaw = profile_factory(name="Yaw Boakye", wallet="0xe11ba2b4d45eaed5996cd0823791e0c93114882d")
    kofi = profile_factory(name="Kofi Mensah", wallet="0xd03ea8624c8c5987235048901fb614fdca89b117")
    ama = profile_factory(name="Ama Owusu", wallet=AMA)
    officer = profile_factory(name="Abena Sarpong", roles=["id_officer"])
    assert privacy.can_see_private(kofi, parcel) and privacy.can_see_private(yaw, parcel)
    assert not privacy.can_see_private(ama, parcel) and not privacy.can_see_private(None, parcel)
    assert privacy.can_see_private(officer, parcel)
    assert privacy.shown_name(ama, "GH-a6e02fa9") is None
    assert privacy.shown_name(kofi, "GH-a6e02fa9") == "Kofi Mensah"
    assert privacy.shown_name(officer, "GH-a6e02fa9") == "Kofi Mensah"
    anon = api.get("/api/v1/parcels/ga-brk-0001").json()
    assert anon["owner"] == {"public_id": "GH-a6e02fa9", "name": None, "kind": "citizen", "label": "GH-a6e02fa9"}
    assert anon["fees"] is None and anon["visibility"] == "public"
    mine = Caller(kofi).get("/api/v1/parcels/GA-BRK-0001").json()
    assert mine["owner"]["name"] == "Kofi Mensah" and mine["fees"]["count"] == 0 and mine["viewer"]["is_owner"]
    assert api.get("/api/v1/parcels/GA-BRK-0001/receipt").json()["error"]["code"] == "PRIVATE"
    assert Caller(ama).get("/api/v1/parcels/GA-BRK-0001/payments").status_code == 403
    assert Caller(yaw).get("/api/v1/parcels/GA-BRK-0001/payments").status_code == 200
    assert api.get("/api/v1/parcels/GA-BRK-0099").json()["error"]["message"] == "No parcel called GA-BRK-0099."


@pytest.mark.django_db
def test_role_permissions(profile_factory):
    ama = Caller(profile_factory(wallet=AMA))
    officer = Caller(profile_factory(roles=["id_officer"]))
    r = officer.post("/api/v1/applications/APP-14/approve")
    assert r.status_code == 403 and r.json()["error"]["message"] == "Only the registrar can approve a registration"
    assert ama.get("/api/v1/review/queue").status_code == 403
    assert officer.get("/api/v1/review/counts").json()["identities"] == 0
    r = ama.post("/api/v1/applications", {})
    assert r.status_code == 403 and r.json()["error"]["code"] == "IDENTITY_NOT_VERIFIED"
    nowallet = Caller(profile_factory())
    assert nowallet.post("/api/v1/identity/submit", {}).json()["error"]["code"] == "WALLET_REQUIRED"
    assert ama.get("/api/v1/admin/officers").status_code == 403


# ---------------------------------------------------------------- enquiries, notifications, rate limits (A7, A8, D1)
@pytest.mark.django_db
def test_enquiry_privacy_and_rate_limit(parcel, profile_factory, api, django_capture_on_commit_callbacks):
    from django.core import mail
    kofi = profile_factory(name="Kofi Mensah", email="kofi@example.com",
                           wallet="0xd03ea8624c8c5987235048901fb614fdca89b117")
    body = {"name": "Kojo Appiah", "contact": "024 000 0000", "message": "Is it available?"}
    with django_capture_on_commit_callbacks(execute=True):
        r = api.post("/api/v1/parcels/GA-BRK-0001/enquiries", body, format="json")
    assert r.status_code == 201 and set(r.json()) == {"id", "parcel_id", "status", "message"}
    assert "GH-a6e02fa9" not in r.content.decode() and "Kofi" not in r.content.decode()
    owner = Caller(kofi)
    inbox = owner.get("/api/v1/me/enquiries?parcel_id=GA-BRK-0001").json()
    assert inbox["count"] == 1 and inbox["new"] == 1 and inbox["results"][0]["name"] == "Kojo Appiah"
    n = owner.get("/api/v1/me/notifications").json()
    assert n["unread"] == 1 and n["results"][0]["kind"] == "enquiry_received"
    assert len(mail.outbox) == 1 and "024 000 0000" in mail.outbox[0].body
    eid = inbox["results"][0]["id"]
    assert owner.patch(f"/api/v1/enquiries/{eid}", {"status": "answered"}).json()["status"] == "answered"
    assert Caller(profile_factory()).patch(f"/api/v1/enquiries/{eid}", {"status": "read"}).status_code == 404
    assert owner.post("/api/v1/me/notifications/read", {"all": True}).json() == {"unread": 0}
    r = owner.post("/api/v1/parcels/GA-BRK-0001/enquiries", body)
    assert r.status_code == 403 and r.json()["error"]["message"] == "You own this parcel."
    codes = [api.post("/api/v1/parcels/GA-BRK-0001/enquiries", body, format="json").status_code for _ in range(5)]
    assert codes == [201, 201, 201, 201, 429]
    r = api.post("/api/v1/parcels/GA-BRK-0001/enquiries", body, format="json")
    assert r.status_code == 429 and r.json()["error"]["code"] == "RATE_LIMITED" and int(r["Retry-After"]) > 0


@pytest.mark.django_db
def test_role_notifications_read_per_officer(profile_factory):
    from django.utils import timezone

    from landchain.notifications.service import notify
    notify(kind="application_submitted", text="New title application GA-BRK-0015 waiting for your review",
           recipient_role="registrar", at=timezone.now())
    a, b = Caller(profile_factory(roles=["registrar"])), Caller(profile_factory(roles=["registrar"]))
    assert a.get("/api/v1/me/notifications").json()["results"][0]["audience"] == "role:Registrar"
    a.post("/api/v1/me/notifications/read", {"all": True})
    assert a.get("/api/v1/me/notifications?unread=true").json()["count"] == 0
    assert b.get("/api/v1/me/notifications?unread=true").json()["count"] == 1


@pytest.mark.django_db
def test_idempotency_replay_and_conflict(profile_factory):
    c = Caller(profile_factory(roles=["admin"]))
    key = str(uuid.uuid4())
    body = {"email": "nobody@example.com", "roles": ["registrar"]}
    r1 = c.post("/api/v1/admin/officers", body, HTTP_IDEMPOTENCY_KEY=key)
    r2 = c.post("/api/v1/admin/officers", body, HTTP_IDEMPOTENCY_KEY=key)
    assert r1.status_code == r2.status_code == 404 and r2["Idempotent-Replayed"] == "true"
    r3 = c.post("/api/v1/admin/officers", {**body, "roles": ["admin"]}, HTTP_IDEMPOTENCY_KEY=key)
    assert r3.status_code == 409 and r3.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"


@pytest.mark.django_db
def test_officer_admin(profile_factory):
    admin = Caller(profile_factory(roles=["admin"]))
    target = profile_factory(email="kwame@lands.gov.gh", name="Kwame")
    r = admin.post("/api/v1/admin/officers", {"email": "kwame@lands.gov.gh", "roles": ["registrar"]})
    assert r.status_code == 200 and r.json()["roles"] == ["registrar"]
    assert admin.delete(f"/api/v1/admin/officers/{target.supabase_user_id}").status_code == 204
    target.refresh_from_db()
    assert target.roles == []


@pytest.mark.django_db
def test_documents_vault(parcel, profile_factory, tmp_path, settings):
    from django.core.files.uploadedfile import SimpleUploadedFile

    from landchain.chain.encoding import file_fingerprint
    from landchain.registry.models import ParcelDoc
    settings.VAULT_LOCAL_DIR = str(tmp_path)
    data = b"%PDF-1.4 site plan for GA-BRK-0001"
    sha = file_fingerprint(data)
    kofi = Caller(profile_factory(wallet="0xd03ea8624c8c5987235048901fb614fdca89b117"))
    r = kofi.client.post("/api/v1/documents", {"file": SimpleUploadedFile("site-plan-kofi.pdf", data),
                                              "doc_type": "Site plan", "sha256": sha}, format="multipart")
    assert r.status_code == 201 and r.json()["sha256"] == sha and r.json()["status"] == "staged"
    r = kofi.client.post("/api/v1/documents", {"file": SimpleUploadedFile("x.pdf", data), "doc_type": "Site plan",
                                              "sha256": "0x" + "1" * 64}, format="multipart")
    assert r.json()["error"]["code"] == "HASH_MISMATCH"
    r = kofi.client.post("/api/v1/documents", {"file": SimpleUploadedFile("x.exe", b"MZ..."),
                                              "doc_type": "Site plan"}, format="multipart")
    assert r.status_code == 415
    ParcelDoc.objects.create(parcel=parcel, position=0, doc_type="Site plan", sha256=sha)
    other = Caller(profile_factory(wallet=AMA))
    assert other.get(f"/api/v1/documents/{sha}/url?parcel_id=GA-BRK-0001").json()["error"]["code"] == "PRIVATE"
    r = kofi.get(f"/api/v1/documents/{sha}/url?parcel_id=GA-BRK-0001")
    assert r.status_code == 200 and r.json()["name"] == "site-plan-kofi.pdf"
    from rest_framework.test import APIClient
    assert APIClient().get(r.json()["url"]).content == data
    officer = Caller(profile_factory(roles=["registrar"]))
    assert officer.get(f"/api/v1/documents/{sha}/url?parcel_id=GA-BRK-0001").status_code == 200
    anon = APIClient()
    r = anon.post("/api/v1/parcels/GA-BRK-0001/documents/check", {"sha256": sha}, format="json")
    assert r.json()["match"] is True and r.json()["doc_type"] == "Site plan"
    r = anon.post("/api/v1/parcels/GA-BRK-0001/documents/check", {"sha256": "0x" + "2" * 64}, format="json")
    assert r.json()["match"] is False


@pytest.mark.django_db
def test_parcel_lists(parcel, api):
    r = api.get("/api/v1/parcels")
    assert r.json()["count"] == 1 and r.json()["results"][0]["owners_count"] == 2
    g = api.get("/api/v1/parcels?format=geojson").json()
    assert g["type"] == "FeatureCollection" and g["features"][0]["geometry"]["coordinates"][0][0] == [-0.23, 5.75]
    assert api.get("/api/v1/parcels/search?q=%231").json()["best"] == "GA-BRK-0001"
    assert api.get("/api/v1/parcels/search?q=GH-a6e0").json()["best"] == "GA-BRK-0001"
    assert api.get("/api/v1/parcels/next-id?prefix=GA-BRK").json() == {"parcel_id": "GA-BRK-0002"}
    s = api.get("/api/v1/stats").json()
    assert s["registered_titles"] == 1 and s["title_holders"] == 1
