"""The two functions every write endpoint calls (task B4, spec 6.2, 6.3 and section 15). Owner: Person B.

Interface (frozen in J1):

    prepare(*, profile, contract, function, args, label, success, action=None, idempotency_key=None) -> TxIntent
        Citizen transaction. Simulates from the citizen's wallet, estimates gas x1.2 and stores the unsigned tx
        in a TxIntent (status awaiting_signature, expires in 15 min). The UI signs it with MetaMask and reports
        the hash (POST /chain/intents/{id}/submitted), or uses dev-sign on the local demo.

    write(*, signer, contract, function, args, label, success, by, target, note=None, request=None,
          action=None, idempotency_key=None) -> TxIntent
        Officer transaction. signer is "registrar" | "id_officer" | "admin". Simulates from the role wallet,
        records OfficerAction (who pressed the button), and queues signer.send on that wallet's queue.

Both raise ChainRevert (422, with the contract's own sentence) when the simulation refuses, after writing a
RevertLog row so the refusal shows in the activity log. No gas is spent on a refusal.

    wait_for(intent, timeout=30) -> TxIntent      used by ?wait=true
    confirm_indexed(up_to_block)                   called by the indexer after each pass (task C8)
"""
from __future__ import annotations

import logging
import time
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from eth_account import Account
from web3 import Web3

from landchain.core.errors import ApiError, ChainRevert, ChainUnavailable, Conflict, SignerUnavailable

from . import client, simulate
from .encoding import public_id
from .models import OfficerAction, RevertLog, TxIntent

log = logging.getLogger("landchain.chain")

INTENT_TTL = timedelta(minutes=15)
ROLE_CONST = {"registrar": "REGISTRAR_ROLE", "id_officer": "ID_OFFICER_ROLE", "admin": "DEFAULT_ADMIN_ROLE"}
SIGNER_MODE = {"registrar": TxIntent.Signer.BACKEND_REGISTRAR, "id_officer": TxIntent.Signer.BACKEND_ID_OFFICER,
               "admin": TxIntent.Signer.BACKEND_ADMIN}
KEY_SETTING = {"registrar": "REGISTRAR_SIGNER_KEY", "id_officer": "ID_OFFICER_SIGNER_KEY",
               "admin": "ADMIN_SIGNER_KEY"}


# ---------------------------------------------------------------- helpers
def jsonable(v):
    if isinstance(v, bytes | bytearray):
        return "0x" + bytes(v).hex()
    if isinstance(v, list | tuple):
        return [jsonable(x) for x in v]
    if isinstance(v, dict):
        return {k: jsonable(x) for k, x in v.items()}
    if hasattr(v, "hex") and not isinstance(v, str | int):
        return v.hex()
    return v


def _idem_uuid(key: str | None):
    if not key:
        return None
    try:
        return uuid.UUID(str(key))
    except ValueError:
        return uuid.uuid5(uuid.NAMESPACE_URL, str(key))


def _existing(profile, key, function):
    if key is None:
        return None
    it = TxIntent.objects.filter(created_by=profile, idempotency_key=key).first()
    if it and it.function != function:
        raise Conflict("This Idempotency-Key was already used for a different action.", code="IDEMPOTENCY_CONFLICT")
    return it


def log_revert(*, contract, function, label, from_address, error, intent=None):
    RevertLog.objects.create(
        chain_id=settings.CHAIN_ID, contract=contract, function=function, args_label=label or "",
        from_address=(from_address or "").lower(), from_public_id=public_id(from_address) if from_address else "",
        error=error, intent=intent)


def _fn(contract: str, function: str, args):
    c = client.contract(contract)
    return c.functions[function](*args), c.address


def signer_key(role: str) -> str:
    return getattr(settings, KEY_SETTING[role], "") or ""


def signer_address(role: str) -> str:
    """Address of the role wallet: from its key, or (local demo) the first on-chain holder of the role."""
    key = signer_key(role)
    if key:
        return Account.from_key(key).address.lower()
    if settings.CHAIN_ALLOW_UNLOCKED_SIGNING:
        acl = client.contract("LandAccessControl")
        try:
            role_id = acl.functions[ROLE_CONST[role]]().call()
            if acl.functions.getRoleMemberCount(role_id).call() > 0:
                addr = acl.functions.getRoleMember(role_id, 0).call().lower()
                if addr in [a.lower() for a in client.w3().eth.accounts]:
                    return addr
        except Exception as e:
            if simulate.is_connection_error(e):
                raise ChainUnavailable(client.unreachable_message()) from e
            raise
    raise SignerUnavailable(f"The {role.replace('_', ' ')} signer wallet is not configured. "
                            f"Set {KEY_SETTING[role]}.")


# ---------------------------------------------------------------- prepare (citizen)
def prepare(*, profile, contract: str, function: str, args, label: str, success: str, action: str | None = None,
            idempotency_key=None) -> TxIntent:
    key = _idem_uuid(idempotency_key)
    existing = _existing(profile, key, function)
    if existing:
        return existing
    from_address = profile.wallet_address
    fn, to = _fn(contract, function, args)
    try:
        simulate.simulate(fn, from_address)
        gas = simulate.estimate_gas(fn, from_address)
    except ChainRevert as e:
        log_revert(contract=contract, function=function, label=label, from_address=from_address, error=e.message)
        raise
    data = fn._encode_transaction_data()
    try:
        return TxIntent.objects.create(
            chain_id=settings.CHAIN_ID, action=action or function, contract=contract, function=function,
            args_json=jsonable(list(args)), args_label=label, success_message=success,
            signer_mode=TxIntent.Signer.WALLET, from_address=from_address.lower(), to_address=to.lower(),
            data=data, gas_limit=gas, status=TxIntent.Status.AWAITING_SIGNATURE, idempotency_key=key,
            created_by=profile, expires_at=timezone.now() + INTENT_TTL)
    except IntegrityError:
        return TxIntent.objects.get(created_by=profile, idempotency_key=key)


def unsigned_tx(intent: TxIntent) -> dict:
    return {"from": intent.from_address, "to": intent.to_address, "data": intent.data, "value": "0x0",
            "gas": hex(intent.gas_limit), "chainId": hex(intent.chain_id)}


# ---------------------------------------------------------------- write (officer)
def write(*, signer: str, contract: str, function: str, args, label: str, success: str, by, target: str,
          note: str | None = None, request=None, action: str | None = None, idempotency_key=None) -> TxIntent:
    key = _idem_uuid(idempotency_key)
    existing = _existing(by, key, function)
    if existing:
        return existing
    from_address = signer_address(signer)
    fn, to = _fn(contract, function, args)
    try:
        simulate.simulate(fn, from_address)
        gas = simulate.estimate_gas(fn, from_address)
    except ChainRevert as e:
        log_revert(contract=contract, function=function, label=label, from_address=from_address, error=e.message)
        if e.status_code == 403:  # the role wallet lost its on-chain role: alert admins
            log.error("Signer %s (%s) refused with: %s", signer, from_address, e.message)
        raise
    with transaction.atomic():
        try:
            intent = TxIntent.objects.create(
                chain_id=settings.CHAIN_ID, action=action or function, contract=contract, function=function,
                args_json=jsonable(list(args)), args_label=label, success_message=success,
                signer_mode=SIGNER_MODE[signer], from_address=from_address, to_address=to.lower(),
                data=fn._encode_transaction_data(), gas_limit=gas, status=TxIntent.Status.QUEUED,
                idempotency_key=key, created_by=by)
        except IntegrityError:
            return TxIntent.objects.get(created_by=by, idempotency_key=key)
        claims = getattr(getattr(request, "user", None), "claims", {}) or {}
        sid = claims.get("session_id")
        OfficerAction.objects.create(
            intent=intent, officer=by, role=signer, action=action or function, target=target, reason=note or None,
            session_id=_idem_uuid(sid) if sid else None,
            ip=(request.META.get("REMOTE_ADDR") if request is not None else None))
        transaction.on_commit(lambda: enqueue_send(intent.id, signer))
    return intent


def enqueue_send(intent_id: str, signer: str):
    from .tasks import signer_send
    signer_send.apply_async(args=[intent_id], queue=f"signer.{signer}")


# ---------------------------------------------------------------- sending
def _fee_fields(w3) -> dict:
    try:
        base = w3.eth.get_block("latest").get("baseFeePerGas")
    except Exception:
        base = None
    if base is None:
        return {"gasPrice": w3.eth.gas_price}
    priority = w3.to_wei(1, "gwei") if settings.CHAIN_ID != 1337 else 0
    return {"maxFeePerGas": 2 * int(base) + priority, "maxPriorityFeePerGas": priority}


def _advisory_lock(cursor, address: str):
    cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", [address.lower()])


def send_intent(intent_id: str):
    """signer.send body: re-simulate, sign with the role wallet, send, store the hash, wait for the receipt."""
    role = {v: k for k, v in SIGNER_MODE.items()}
    with transaction.atomic():
        intent = TxIntent.objects.select_for_update().get(pk=intent_id)
        if intent.status != TxIntent.Status.QUEUED:
            return intent
        signer = role[intent.signer_mode]
        w3 = client.w3()
        fn, _ = _fn(intent.contract, intent.function, intent.args_json)
        try:
            simulate.simulate(fn, intent.from_address)
        except ChainRevert as e:
            intent.status, intent.revert_reason, intent.error = TxIntent.Status.FAILED, e.message, e.message
            intent.save(update_fields=["status", "revert_reason", "error", "updated_at"])
            log_revert(contract=intent.contract, function=intent.function, label=intent.args_label,
                       from_address=intent.from_address, error=e.message, intent=intent)
            return intent
        from django.db import connection
        with connection.cursor() as cur:
            _advisory_lock(cur, intent.from_address)
            tx_hash = None
            for attempt in range(2):
                try:
                    tx = {"to": client.checksum(intent.to_address), "data": intent.data, "gas": intent.gas_limit,
                          "chainId": intent.chain_id, "value": 0,
                          "nonce": w3.eth.get_transaction_count(client.checksum(intent.from_address), "pending"),
                          **_fee_fields(w3)}
                    key = signer_key(signer)
                    if key:
                        signed = Account.sign_transaction(tx, key)
                        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
                    else:
                        tx["from"] = client.checksum(intent.from_address)
                        tx_hash = w3.eth.send_transaction(tx)
                    break
                except Exception as e:
                    if "nonce too low" in str(e).lower() and attempt == 0:
                        continue
                    msg = simulate.revert_reason(e) if not simulate.is_connection_error(e) \
                        else client.unreachable_message()
                    intent.status, intent.error = TxIntent.Status.FAILED, msg
                    intent.save(update_fields=["status", "error", "updated_at"])
                    return intent
        intent.tx_hash = Web3.to_hex(tx_hash).lower()
        intent.status = TxIntent.Status.SUBMITTED
        intent.submitted_at = timezone.now()
        intent.save(update_fields=["tx_hash", "status", "submitted_at", "updated_at"])
    poll_receipt(intent, timeout=20 if settings.CHAIN_ID == 1337 else 0)
    return intent


def poll_receipt(intent: TxIntent, timeout: float = 0) -> TxIntent:
    """Fetch the receipt for a submitted intent; mark mined / reverted. Waits up to `timeout` seconds."""
    if intent.status != TxIntent.Status.SUBMITTED or not intent.tx_hash:
        return intent
    w3 = client.w3()
    deadline = time.monotonic() + timeout
    while True:
        try:
            receipt = w3.eth.get_transaction_receipt(intent.tx_hash)
        except Exception:
            receipt = None
        if receipt is not None:
            apply_receipt(intent, receipt)
            return intent
        if time.monotonic() >= deadline:
            return intent
        time.sleep(0.25)


def apply_receipt(intent: TxIntent, receipt) -> None:
    intent.block_number = int(receipt["blockNumber"])
    if int(receipt["status"]) == 1:
        intent.status = TxIntent.Status.MINED
    else:
        intent.status = TxIntent.Status.REVERTED
        intent.revert_reason = _mined_revert_reason(intent, receipt) or "Transaction reverted"
        log_revert(contract=intent.contract, function=intent.function, label=intent.args_label,
                   from_address=intent.from_address, error=intent.revert_reason, intent=intent)
    intent.save(update_fields=["block_number", "status", "revert_reason", "updated_at"])
    if intent.status == TxIntent.Status.MINED and settings.INDEXER_INLINE:
        run_indexer_inline()


def _mined_revert_reason(intent, receipt) -> str | None:
    try:
        client.w3().eth.call({"from": client.checksum(intent.from_address), "to": client.checksum(intent.to_address),
                              "data": intent.data}, int(receipt["blockNumber"]) - 1)
    except Exception as e:
        return simulate.revert_reason(e)
    return None


# ---------------------------------------------------------------- confirmation (called by the indexer)
def confirm_indexed(up_to_block: int, result_for=None) -> int:
    """Mark mined intents whose block is indexed (and has CHAIN_CONFIRMATIONS) as confirmed. Returns count."""
    n = 0
    for intent in TxIntent.objects.filter(status=TxIntent.Status.MINED, block_number__lte=up_to_block,
                                          chain_id=settings.CHAIN_ID):
        intent.status = TxIntent.Status.CONFIRMED
        if result_for is not None and intent.tx_hash:
            intent.result_json = result_for(intent) or intent.result_json
        intent.save(update_fields=["status", "result_json", "updated_at"])
        n += 1
    return n


def run_indexer_inline():
    try:
        from landchain.indexer.runner import run_once
        run_once()
    except Exception:  # the beat task will pick it up
        log.exception("Inline indexer pass failed")


def wait_for(intent: TxIntent, timeout: float = 30.0) -> TxIntent:
    deadline = time.monotonic() + timeout
    while True:
        intent.refresh_from_db()
        if intent.is_final:
            return intent
        if intent.status == TxIntent.Status.SUBMITTED:
            poll_receipt(intent, timeout=0)
        if intent.status == TxIntent.Status.MINED and settings.INDEXER_INLINE:
            run_indexer_inline()
            intent.refresh_from_db()
            if intent.is_final:
                return intent
        if time.monotonic() >= deadline:
            return intent
        time.sleep(0.3)


# ---------------------------------------------------------------- wallet intents (B5)
def verify_submitted(intent: TxIntent, tx_hash: str, lookup_timeout: float | None = None) -> TxIntent:
    """The UI reports a hash: check the chain transaction equals what was prepared, then watch it."""
    if intent.status == TxIntent.Status.EXPIRED or (
            intent.status == TxIntent.Status.AWAITING_SIGNATURE and intent.expires_at
            and intent.expires_at < timezone.now()):
        if intent.status != TxIntent.Status.EXPIRED:
            intent.status = TxIntent.Status.EXPIRED
            intent.save(update_fields=["status", "updated_at"])
        raise ApiError("This transaction expired. Start again.", code="INTENT_EXPIRED", status_code=410)
    if intent.status != TxIntent.Status.AWAITING_SIGNATURE:
        if intent.tx_hash and intent.tx_hash == tx_hash.lower():
            return intent
        raise Conflict("This action is no longer waiting for a signature.", code="INTENT_NOT_AWAITING")
    w3 = client.w3()
    timeout = lookup_timeout if lookup_timeout is not None else getattr(settings, "TX_LOOKUP_TIMEOUT", 60)
    deadline = time.monotonic() + timeout
    tx = None
    while tx is None:
        try:
            tx = w3.eth.get_transaction(tx_hash)
        except Exception:
            tx = None
        if tx is None:
            if time.monotonic() >= deadline:
                raise ApiError("Transaction not found on the chain.", code="TX_NOT_FOUND", status_code=404)
            time.sleep(0.5)
    data = Web3.to_hex(tx["input"]).lower()
    if (tx["to"] or "").lower() != intent.to_address or data != intent.data.lower() \
            or tx["from"].lower() != intent.from_address:
        raise ApiError("This transaction is not the one prepared for this action.", code="TX_MISMATCH",
                       status_code=422)
    intent.tx_hash = tx_hash.lower()
    intent.status = TxIntent.Status.SUBMITTED
    intent.submitted_at = timezone.now()
    try:
        intent.save(update_fields=["tx_hash", "status", "submitted_at", "updated_at"])
    except IntegrityError as e:
        raise ApiError("This transaction is already linked to another action.", code="TX_MISMATCH",
                       status_code=422) from e
    poll_receipt(intent, timeout=5 if settings.CHAIN_ID == 1337 else 0)
    return intent


def dev_sign(intent: TxIntent) -> TxIntent:
    """Local demo: send the prepared tx from Ganache's unlocked account."""
    if intent.status != TxIntent.Status.AWAITING_SIGNATURE:
        raise Conflict("This action is no longer waiting for a signature.", code="INTENT_NOT_AWAITING")
    w3 = client.w3()
    unlocked = [a.lower() for a in w3.eth.accounts]
    if intent.from_address not in unlocked:
        raise ApiError("This account can't sign here. Connect it in MetaMask or pick a demo account.",
                       code="CANNOT_SIGN", status_code=403)
    try:
        h = w3.eth.send_transaction({"from": client.checksum(intent.from_address),
                                     "to": client.checksum(intent.to_address), "data": intent.data,
                                     "gas": intent.gas_limit, "value": 0})
    except Exception as e:
        reason = simulate.revert_reason(e)
        intent.status, intent.error, intent.revert_reason = TxIntent.Status.FAILED, reason, reason
        intent.save(update_fields=["status", "error", "revert_reason", "updated_at"])
        log_revert(contract=intent.contract, function=intent.function, label=intent.args_label,
                   from_address=intent.from_address, error=reason, intent=intent)
        raise ChainRevert(reason) from e
    intent.signer_mode = TxIntent.Signer.DEV_UNLOCKED
    intent.tx_hash = Web3.to_hex(h).lower()
    intent.status = TxIntent.Status.SUBMITTED
    intent.submitted_at = timezone.now()
    intent.save(update_fields=["signer_mode", "tx_hash", "status", "submitted_at", "updated_at"])
    poll_receipt(intent, timeout=20)
    return intent


def wallet_rejected(intent: TxIntent, message: str | None = None) -> TxIntent:
    if intent.status != TxIntent.Status.AWAITING_SIGNATURE:
        raise Conflict("This action is no longer waiting for a signature.", code="INTENT_NOT_AWAITING")
    intent.status = TxIntent.Status.FAILED
    intent.error = "You cancelled the transaction in your wallet"
    intent.save(update_fields=["status", "error", "updated_at"])
    log_revert(contract=intent.contract, function=intent.function, label=intent.args_label,
               from_address=intent.from_address, error=intent.error, intent=intent)
    return intent


def watch_intents() -> dict:
    """intents.watch: receipts for submitted intents, expiry of unsigned ones, failure of unknown hashes."""
    now = timezone.now()
    expired = TxIntent.objects.filter(status=TxIntent.Status.AWAITING_SIGNATURE, expires_at__lt=now) \
        .update(status=TxIntent.Status.EXPIRED, updated_at=now)
    mined = failed = 0
    w3 = client.w3()
    for intent in TxIntent.objects.filter(status=TxIntent.Status.SUBMITTED, chain_id=settings.CHAIN_ID):
        poll_receipt(intent, timeout=0)
        if intent.status != TxIntent.Status.SUBMITTED:
            mined += 1
            continue
        if intent.submitted_at and intent.submitted_at < now - timedelta(minutes=10):
            try:
                known = w3.eth.get_transaction(intent.tx_hash) is not None
            except Exception:
                known = False
            if not known:
                intent.status, intent.error = TxIntent.Status.FAILED, "The transaction was dropped or replaced."
                intent.save(update_fields=["status", "error", "updated_at"])
                failed += 1
    return {"expired": expired, "mined": mined, "failed": failed}
