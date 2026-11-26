"""Acceptance tests from spec section 17, against Ganache seeded with `npm run setup:local` (task J3).

Skipped unless the chain is reachable. Re-runnable on the same chain: the full-life test creates a new wallet,
funds it from a spare Ganache account and signs locally, exactly as MetaMask would (eth_sendRawTransaction).
"""
from __future__ import annotations

import random

import pytest
from eth_account import Account
from eth_account.messages import encode_defunct

from tests.conftest import Caller

pytestmark = pytest.mark.chain


def _w3():
    from landchain.chain import client
    return client.w3()


def sign_and_submit(caller: Caller, intent: dict, key: str) -> dict:
    """What the UI does with MetaMask: send intent.tx, then report the hash."""
    w3 = _w3()
    tx = intent["tx"]
    acct = Account.from_key(key)
    raw = Account.sign_transaction({
        "to": w3.to_checksum_address(tx["to"]), "data": tx["data"], "value": 0, "gas": int(tx["gas"], 16),
        "chainId": int(tx["chainId"], 16), "nonce": w3.eth.get_transaction_count(acct.address, "pending"),
        "gasPrice": w3.eth.gas_price}, key)
    h = w3.eth.send_raw_transaction(raw.raw_transaction).hex()
    h = h if h.startswith("0x") else "0x" + h
    r = caller.post(f"/api/v1/chain/intents/{intent['id']}/submitted", {"tx_hash": h})
    assert r.status_code == 200, r.content
    return poll(caller, intent["id"])


def poll(caller: Caller, intent_id: str) -> dict:
    import time
    for _ in range(60):
        it = caller.get(f"/api/v1/chain/intents/{intent_id}").json()
        if it["status"] in ("confirmed", "reverted", "failed", "expired"):
            return it
        time.sleep(0.25)
    return it


def test_1_indexer_reproduces_register(demo, api):
    p2 = api.get("/api/v1/parcels/GA-BRK-0002").json()
    assert p2["plan_number"].startswith("SER B") and p2["status"] == "registered"
    assert [d["doc_type"] for d in p2["documents"]] == ["Site plan", "Indenture", "Search report"]
    assert all(d["file_available"] is False for d in p2["documents"])
    ama = demo["ama"]
    kinds = [x["kind"] for x in ama.get("/api/v1/parcels/GA-BRK-0002/payments").json()["results"]]
    assert kinds[:3] == ["Official search", "Stamp duty", "First registration"]
    assert api.get("/api/v1/parcels/GA-BRK-0006").json()["status"] == "transfer_pending"
    assert api.get("/api/v1/parcels/GA-BRK-0013").json()["status"] == "pending"
    p1 = demo["registrar"].get("/api/v1/parcels/GA-BRK-0001").json()
    assert p1["owner"]["name"] == "Kofi Mensah" and [o["name"] for o in p1["owners"]] == ["Yaw Boakye", "Kofi Mensah"]
    assert "Transfer" in [h["type"] for h in api.get("/api/v1/parcels/GA-BRK-0001/history").json()["results"]]
    status = api.get("/api/v1/chain/status").json()
    assert status["kind"] == "ok" and status["contracts_match"] and status["lag_blocks"] == 0


def test_2_and_3_tamper_attempts(demo, api):
    r = demo["kofi"].post("/api/v1/transfers", {"parcel_id": "GA-BRK-0002", "to_public_id": demo["yaw"].profile.public_id})
    assert r.status_code == 422 and r.json()["error"]["message"] == "Only the owner can transfer this title"
    rev = api.get("/api/v1/activity?status=Reverted").json()["results"]
    assert any(x["error"] == "Only the owner can transfer this title" and "GA-BRK-0002" in x["args_label"] for x in rev)
    r = demo["abena"].post("/api/v1/applications/APP-14/approve")
    assert r.status_code == 403 and r.json()["error"]["message"] == "Only the registrar can approve a registration"


def test_4_full_life_with_a_new_wallet(demo, api, tmp_path, settings):
    """Link wallet → identity → verify → upload 3 docs → apply → fees → approve → transfer → approve."""
    from django.core.files.uploadedfile import SimpleUploadedFile

    from landchain.chain.encoding import card_hash
    settings.VAULT_LOCAL_DIR = str(tmp_path)
    w3 = _w3()
    acct = Account.create()
    w3.eth.send_transaction({"from": w3.eth.accounts[11], "to": acct.address, "value": w3.to_wei(5, "ether")})
    import uuid

    from landchain.accounts.models import Profile
    me = Caller(Profile.objects.create(supabase_user_id=uuid.uuid4(), email=f"{uuid.uuid4().hex[:6]}@x.com"))

    # wallet linking (A4)
    r = me.post("/api/v1/auth/wallet/nonce", {"address": acct.address})
    assert r.status_code == 200
    msg = r.json()["message"]
    bad = Account.create().sign_message(encode_defunct(text=msg)).signature.hex()
    assert me.post("/api/v1/auth/wallet/verify", {"message": msg, "signature": bad}).json()["error"]["code"] == \
        "SIGNATURE_INVALID"
    sig = acct.sign_message(encode_defunct(text=msg)).signature.hex()
    r = me.post("/api/v1/auth/wallet/verify", {"message": msg, "signature": sig})
    assert r.status_code == 200 and r.json()["wallet_address"] == acct.address.lower()
    assert me.post("/api/v1/auth/wallet/verify", {"message": msg, "signature": sig}).json()["error"]["code"] == \
        "NONCE_INVALID"
    r = demo["ama"].post("/api/v1/auth/wallet/nonce", {"address": acct.address})
    assert r.json()["error"]["code"] == "WALLET_ALREADY_LINKED"
    me.profile.refresh_from_db()
    pid = me.profile.public_id

    # identity (B8) through the MetaMask path, with a TX_MISMATCH attempt first
    card = f"GHA-{random.randint(10**8, 10**9 - 1)}-{random.randint(0, 9)}"
    r = me.post("/api/v1/identity/submit", {"card_hash": card_hash(card), "citizenship": "citizen",
                                             "full_name": "New Owner"})
    assert r.status_code == 201 and r.json()["intent"]["status"] == "awaiting_signature"
    intent = r.json()["intent"]
    unrelated = w3.eth.send_transaction({"from": w3.eth.accounts[11], "to": w3.eth.accounts[10], "value": 1}).hex()
    unrelated = unrelated if unrelated.startswith("0x") else "0x" + unrelated
    r = me.post(f"/api/v1/chain/intents/{intent['id']}/submitted", {"tx_hash": unrelated})
    assert r.status_code == 422 and r.json()["error"]["code"] == "TX_MISMATCH"
    assert sign_and_submit(me, intent, acct.key.hex())["status"] == "confirmed"
    assert me.get("/api/v1/me").json()["identity"]["status"] == "pending"
    q = demo["abena"].get("/api/v1/review/queue").json()
    assert any(i["public_id"] == pid and i["name"] == "New Owner" for i in q["identities"]["items"])
    r = demo["abena"].post(f"/api/v1/identities/{pid}/verify?wait=true", {"note": "NIA record checked"})
    assert r.status_code == 200 and r.json()["identity"]["status"] == "verified"

    # documents (D2) and application (D5)
    docs = []
    for t in ("Site plan", "Indenture", "Search report"):
        f = SimpleUploadedFile(f"{t}.pdf", f"%PDF-1.4 {t} {uuid.uuid4()}".encode())
        r = me.client.post("/api/v1/documents", {"file": f, "doc_type": t}, format="multipart")
        assert r.status_code == 201
        docs.append(r.json()["id"])
    lat, lng = 6.5 + random.random(), -1.5 + random.random()
    pillars = [[lat, lng], [lat, lng + 0.002], [lat - 0.0015, lng + 0.002], [lat - 0.0015, lng]]
    parcel_id = f"AS-KUM-{random.randint(1000, 9999)}"
    body = {"parcel_id": parcel_id, "interest": "Customary freehold", "holder": "Asante Stool", "region": "Ashanti",
            "plan_number": "ar 1234/26", "gps_address": "AK-123-4567", "pillars": pillars, "documents": docs[:2]}
    assert me.post("/api/v1/applications", body).json()["error"]["message"] == "Still needed: Search report."
    body["documents"] = docs
    r = me.post("/api/v1/applications", body)
    assert r.status_code == 201, r.content
    assert r.json()["preview"]["acres_x100"] > 0
    it = sign_and_submit(me, r.json()["intent"], acct.key.hex())
    assert it["status"] == "confirmed" and it["result"]["parcel_id"] == parcel_id
    app_id = it["result"]["application_id"]
    detail = me.get(f"/api/v1/parcels/{parcel_id}").json()
    assert detail["status"] == "pending" and detail["plan_number"] == "AR 1234/26"
    assert all(d["file_available"] and d["can_open"] for d in detail["documents"])

    # fees and approval (D4)
    reg = demo["registrar"]
    r = reg.post(f"/api/v1/applications/{app_id}/approve?wait=true")
    assert r.status_code == 422 and r.json()["error"]["message"] == "Record the stamp duty receipt before approving"
    rno = f"GRA-SD-{uuid.uuid4().hex[:8]}"
    r = reg.post(f"/api/v1/parcels/{parcel_id}/payments?wait=true",
                 {"kind": "Stamp duty", "receipt_no": rno, "consideration_ghs": "60000.00"})
    assert r.status_code == 200 and r.json()["payment"]["amount_ghs"] == "600.00"
    assert r.json()["payment"]["receipt_no"] == rno.upper()
    # spec 17 test 6: receipt reuse
    r = reg.post(f"/api/v1/parcels/{parcel_id}/payments?wait=true", {"kind": "Official search", "receipt_no": rno.lower()})
    assert r.status_code == 422 and r.json()["error"]["message"] == "This receipt has already been recorded"
    r = reg.post(f"/api/v1/parcels/{parcel_id}/payments?wait=true",
                 {"kind": "First registration", "receipt_no": f"LC-FR-{uuid.uuid4().hex[:8]}"})
    assert r.status_code == 200
    assert reg.get(f"/api/v1/applications/{app_id}").json()["can_approve"] is True
    r = reg.post(f"/api/v1/applications/{app_id}/approve?wait=true", {"note": "boundary pillars confirmed"},
                 HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
    assert r.status_code == 200 and r.json()["parcel"]["status"] == "registered" and r.json()["parcel"]["title_no"]
    assert me.get("/api/v1/me/notifications").json()["results"][0]["kind"] == "title_issued"

    # transfer (D6): to Ama, fee, approve
    ama = demo["ama"]
    assert me.get(f"/api/v1/identities/lookup?public_id={ama.profile.public_id}").json()["verified"] is True
    r = me.post("/api/v1/transfers", {"parcel_id": parcel_id, "to_public_id": ama.profile.public_id})
    assert r.status_code == 201
    it = sign_and_submit(me, r.json()["intent"], acct.key.hex())
    trf = it["result"]["transfer_id"]
    r = reg.post(f"/api/v1/transfers/{trf}/approve?wait=true")
    assert r.json()["error"]["message"] == "Record the transfer fee before approving"
    r = reg.post(f"/api/v1/parcels/{parcel_id}/payments?wait=true",
                 {"kind": "Transfer", "receipt_no": f"LC-TR-{uuid.uuid4().hex[:8]}", "transfer_id": trf})
    assert r.status_code == 200 and r.json()["payment"]["transfer_id"] == trf
    r = reg.post(f"/api/v1/transfers/{trf}/approve?wait=true")
    assert r.status_code == 200
    owners = [o["public_id"] for o in r.json()["parcel"]["owners"]]
    assert owners == [pid, ama.profile.public_id]
    hist = [h["type"] for h in api.get(f"/api/v1/parcels/{parcel_id}/history").json()["results"]]
    assert hist == ["Application", "Registration", "Transfer requested", "Transfer"]
    rec = me.get(f"/api/v1/parcels/{parcel_id}/receipt").json()   # past owner keeps access
    assert len(rec["transactions"]["items"]) >= 6 and float(rec["transactions"]["owner_signed_eth"]) > 0
    assert me.get(f"/api/v1/parcels/{parcel_id}").json()["viewer"]["was_owner"] is True


def test_5_privacy(demo, api):
    anon = api.get("/api/v1/parcels/GA-BRK-0002").json()
    assert anon["owner"]["name"] is None and all(o["name"] is None for o in anon["owners"]) and anon["fees"] is None
    assert api.get("/api/v1/parcels/GA-BRK-0002/receipt").status_code == 403
    mine = demo["ama"].get("/api/v1/parcels/GA-BRK-0002").json()
    assert mine["owner"]["name"] == "Ama Owusu" and mine["fees"]["count"] >= 3
    pay = demo["ama"].get("/api/v1/parcels/GA-BRK-0002/payments").json()["results"][0]
    assert pay["receipt_no"] is None                                    # plain numbers: officers only
    reg = demo["registrar"].get("/api/v1/parcels/GA-BRK-0002").json()
    assert reg["owner"]["name"] == "Ama Owusu" and reg["visibility"] == "private"
    assert demo["kofi"].get("/api/v1/parcels/GA-BRK-0002/payments").json()["error"]["code"] == "PRIVATE"


def test_8_enquiry_to_unknown_owner(demo, api):
    owner_pid = api.get("/api/v1/parcels/GA-BRK-0003").json()["owner"]["public_id"]
    owner = next(c for c in demo.values() if c.profile.public_id == owner_pid)
    r = api.post("/api/v1/parcels/GA-BRK-0003/enquiries",
                 {"name": "Kojo Appiah", "contact": "024 000 0000", "message": "Is it available?"}, format="json")
    assert r.status_code == 201 and owner_pid not in r.content.decode()
    inbox = owner.get("/api/v1/me/enquiries?parcel_id=GA-BRK-0003").json()
    assert inbox["new"] == 1
    assert owner.patch(f"/api/v1/enquiries/{inbox['results'][0]['id']}", {"status": "answered"}).json()["status"] == \
        "answered"


def test_wallet_cancel_and_dev_sign(demo, api):
    yaw = demo["yaw"]  # owns GA-BRK-0006 with a transfer waiting (TRF-2) in the seed
    p6 = yaw.get("/api/v1/parcels/GA-BRK-0006").json()
    assert p6["viewer"]["can_cancel_transfer"] is True
    trf = p6["open_transfer"]["id"]
    r = yaw.post(f"/api/v1/transfers/{trf}/cancel")
    assert r.status_code == 201
    rej = yaw.post(f"/api/v1/chain/intents/{r.json()['intent']['id']}/rejected-by-wallet",
                   {"code": 4001, "message": "User denied transaction signature."}).json()
    assert rej["status"] == "failed" and rej["error"] == "You cancelled the transaction in your wallet"
    assert api.get("/api/v1/activity?status=Reverted").json()["results"][0]["error"] == \
        "You cancelled the transaction in your wallet"
    # Kofi (not the requester) can't cancel: the contract refuses at prepare time
    r = demo["kofi"].post(f"/api/v1/transfers/{trf}/cancel")
    assert r.status_code == 422 and r.json()["error"]["message"] == "Only the owner who asked can cancel this transfer"
    assert yaw.get("/api/v1/me").json()["counts"]["parcels_owned"] >= 1


def test_10_fresh_chain_rebuilds(demo, api):
    from landchain.indexer.models import IndexerCursor
    from landchain.indexer.runner import run_once
    before = api.get("/api/v1/stats").json()
    IndexerCursor.objects.update(title_registry_address="0x" + "0" * 40)   # as if Ganache was restarted fresh
    run_once()
    after = api.get("/api/v1/stats").json()
    assert {k: v for k, v in after.items() if k != "block"} == {k: v for k, v in before.items() if k != "block"}


def test_admin_signers_and_resync(demo):
    admin = demo["registrar"]
    rows = admin.get("/api/v1/admin/signers").json()["results"]
    assert {r["role"]: r["has_role_on_chain"] for r in rows} == {"registrar": True, "id_officer": True, "admin": True}
    r = admin.post("/api/v1/admin/indexer/resync", {})
    assert r.status_code == 202 and r.json()["from_block"] == 0
    assert admin.get("/api/v1/parcels/GA-BRK-0001").status_code == 200
    assert demo["ama"].post("/api/v1/admin/indexer/resync").status_code == 403
