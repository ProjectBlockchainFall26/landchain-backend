"""Indexer loop (task C3, spec 6.5) with reorg and fresh-chain handling (task C4).

    run_once()  one pass: follow the four contracts' events from the cursor to head - CHAIN_CONFIRMATIONS,
                apply them to the projection, write activity rows, history and notifications, confirm intents.
    resync()    wipe the projection for this chain and re-index from startBlock.

Only one pass runs at a time (Postgres advisory lock), whether it is called by the Celery beat task, the
run_indexer command or ?wait=true on a local demo.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from django.conf import settings
from django.db import connection, transaction
from web3 import Web3

from landchain.chain import client
from landchain.chain import contracts as reg
from landchain.chain.encoding import public_id
from landchain.chain.service import confirm_indexed, jsonable
from landchain.fees.models import Payment
from landchain.registry.models import (
    Application,
    ChainIdentity,
    ChainRole,
    HistoryEvent,
    Parcel,
    TransferRequest,
)

from . import handlers
from .models import ChainBlock, ChainEvent, ChainTx, IndexerCursor

log = logging.getLogger("landchain.indexer")
BATCH = 2000
LOCK_KEY = 74_1337_0001


class _Decoder:
    def __init__(self, dep):
        self.dep = dep
        self.contracts = {n: client.contract(n) for n in reg.NAMES}
        self.by_topic: dict[tuple[str, str], tuple[str, str]] = {}
        for name in self.contracts:
            for item in reg.abi(name):
                if item.get("type") != "event":
                    continue
                sig = f"{item['name']}({','.join(_canonical(i) for i in item['inputs'])})"
                self.by_topic[(dep.address(name), Web3.keccak(text=sig).hex().removeprefix("0x"))] = \
                    (name, item["name"])

    def decode(self, lg):
        topic = Web3.to_hex(lg["topics"][0]).removeprefix("0x") if lg["topics"] else ""
        hit = self.by_topic.get((lg["address"].lower(), topic))
        if not hit:
            return None
        name, event = hit
        ev = self.contracts[name].events[event]().process_log(lg)
        return name, event, jsonable(dict(ev["args"]))

    def function_of(self, tx) -> tuple[str, str]:
        to = (tx.get("to") or "").lower()
        name = self.dep.name_of(to)
        if not name:
            return ("", "constructor" if not to else "call")
        try:
            fn, _ = self.contracts[name].decode_function_input(tx["input"])
            return name, fn.fn_name
        except Exception:
            return name, "call"


def _canonical(inp: dict) -> str:
    t = inp["type"]
    if t.startswith("tuple"):
        return "(" + ",".join(_canonical(c) for c in inp["components"]) + ")" + t[5:]
    return t


def _try_lock() -> bool:
    with connection.cursor() as cur:
        cur.execute("SELECT pg_try_advisory_xact_lock(%s)", [LOCK_KEY])
        return bool(cur.fetchone()[0])


def wipe(chain_id: int):
    """Delete the projection for this chain (single-chain deployment: every projection row)."""
    from landchain.notifications.models import Notification
    Notification.objects.filter(source_event__isnull=False).delete()
    HistoryEvent.objects.all().delete()
    Payment.objects.all().delete()
    TransferRequest.objects.all().delete()
    Application.objects.all().delete()
    Parcel.objects.all().delete()
    ChainIdentity.objects.all().delete()
    ChainRole.objects.all().delete()
    ChainTx.objects.filter(chain_id=chain_id).delete()
    ChainEvent.objects.filter(chain_id=chain_id).delete()
    ChainBlock.objects.filter(chain_id=chain_id).delete()
    from landchain.documents.models import Document
    Document.objects.filter(status=Document.Status.ATTACHED).update(status=Document.Status.STAGED,
                                                                    parcel_record_id=None, attached_at=None)


def _forget_old_chain(chain_id: int):
    """Intents still open against a chain that is gone (Ganache restarted, contracts redeployed) can never
    confirm. A fresh Ganache reuses tx hashes and payment ids; service.claim_tx_hash and refresh_payment
    move those over to the new rows."""
    from landchain.chain.models import TxIntent
    TxIntent.objects.filter(chain_id=chain_id).exclude(status__in=TxIntent.FINAL).update(
        status="expired", error="The chain was reset before this transaction was confirmed")


def _reset_cursor(cursor: IndexerCursor, dep, from_block: int | None = None, *, fresh: bool = False):
    wipe(cursor.chain_id)
    if fresh:
        _forget_old_chain(cursor.chain_id)
    start = dep.start_block if from_block is None else from_block
    cursor.title_registry_address = dep.address("TitleRegistry")
    cursor.last_block = start - 1
    cursor.last_block_hash = ""
    cursor.save()


def _check_fork(cursor: IndexerCursor, dep, w3, head: int) -> str | None:
    """Return 'fresh' (new chain / redeploy), 'reorg', or None."""
    if cursor.title_registry_address != dep.address("TitleRegistry") or cursor.last_block > head:
        return "fresh"
    if cursor.last_block >= 0 and cursor.last_block_hash:
        try:
            h = Web3.to_hex(w3.eth.get_block(cursor.last_block)["hash"]).lower()
        except Exception:
            return "fresh"
        if h != cursor.last_block_hash:
            return "reorg"
    return None


def _rollback_reorg(cursor: IndexerCursor, w3):
    """Find the last block whose stored hash still matches, delete newer rows and rebuild from view functions."""
    blocks = ChainBlock.objects.filter(chain_id=cursor.chain_id, number__lte=cursor.last_block).order_by("-number")
    good = -1
    for b in blocks[:256]:
        try:
            if Web3.to_hex(w3.eth.get_block(b.number)["hash"]).lower() == b.hash:
                good = b.number
                break
        except Exception:
            continue
    ChainEvent.objects.filter(chain_id=cursor.chain_id, block_number__gt=good).delete()
    ChainTx.objects.filter(chain_id=cursor.chain_id, block_number__gt=good).delete()
    ChainBlock.objects.filter(chain_id=cursor.chain_id, number__gt=good).delete()
    HistoryEvent.objects.filter(block_number__gt=good).delete()
    # Rebuild every projection row from the contracts as they are now.
    rebuild_all(max(good, 0))
    cursor.last_block = good
    cursor.last_block_hash = ChainBlock.objects.filter(chain_id=cursor.chain_id, number=good).values_list(
        "hash", flat=True).first() or ""
    cursor.save()


def rebuild_all(block: int):
    t = client.contract("TitleRegistry")
    for rec in range(1, t.functions.parcelCount().call() + 1):
        handlers.refresh_record(rec, block)
    for app in range(1, t.functions.applicationCount().call() + 1):
        handlers.refresh_application(app)
    for trf in range(1, t.functions.transferCount().call() + 1):
        handlers.refresh_transfer(trf)
    fl = client.contract("FeeLedger")
    for pay in range(1, fl.functions.paymentCount().call() + 1):
        handlers.refresh_payment(pay)
    for addr in client.contract("IdentityRegistry").functions.members().call():
        handlers.refresh_identity(addr)
    handlers.refresh_roles()


def run_once(max_batches: int = 50) -> dict:
    """One indexer pass. Returns {"from", "to", "events", "skipped"}."""
    dep = client.deployment()
    w3 = client.w3()
    head = client.head_block()
    with transaction.atomic():
        if not _try_lock():
            return {"skipped": "another indexer pass is running"}
        cursor, _ = IndexerCursor.objects.select_for_update().get_or_create(
            chain_id=settings.CHAIN_ID,
            defaults={"title_registry_address": dep.address("TitleRegistry"), "last_block": dep.start_block - 1})
        fork = _check_fork(cursor, dep, w3, head)
        if fork == "fresh":
            log.warning("New chain or redeployed contracts: re-indexing from block %s", dep.start_block)
            _reset_cursor(cursor, dep, fresh=True)
        elif fork == "reorg":
            log.warning("Reorg detected at block %s", cursor.last_block)
            _rollback_reorg(cursor, w3)

        to_block = head - settings.CHAIN_CONFIRMATIONS
        start = cursor.last_block + 1
        n_events = 0
        if to_block >= start:
            decoder = _Decoder(dep)
            addrs = [client.checksum(a) for a in dep.addresses.values()]
            frm = start
            for _ in range(max_batches):
                if frm > to_block:
                    break
                end = min(frm + BATCH - 1, to_block)
                logs = w3.eth.get_logs({"fromBlock": frm, "toBlock": end, "address": addrs})
                n_events += _apply_logs(cursor, decoder, w3, sorted(
                    logs, key=lambda x: (int(x["blockNumber"]), int(x["logIndex"]))))
                blk = w3.eth.get_block(end)
                _save_block(cursor.chain_id, blk)
                cursor.last_block = end
                cursor.last_block_hash = Web3.to_hex(blk["hash"]).lower()
                cursor.save()
                frm = end + 1
        confirmed = confirm_indexed(cursor.last_block, result_for=handlers.intent_result)
    return {"from": start, "to": cursor.last_block, "events": n_events, "confirmed": confirmed}


def _save_block(chain_id: int, blk) -> datetime:
    at = datetime.fromtimestamp(int(blk["timestamp"]), tz=UTC)
    ChainBlock.objects.update_or_create(chain_id=chain_id, number=int(blk["number"]), defaults={
        "hash": Web3.to_hex(blk["hash"]).lower(), "timestamp": at})
    return at


def _apply_logs(cursor, decoder: _Decoder, w3, logs) -> int:
    chain_id = cursor.chain_id
    block_times: dict[int, datetime] = {}
    pass_ = handlers.Pass()
    txs_seen: dict[str, int] = {}
    n = 0
    for lg in logs:
        decoded = decoder.decode(lg)
        if decoded is None:
            continue
        contract, event, args = decoded
        bn, li = int(lg["blockNumber"]), int(lg["logIndex"])
        tx_hash = Web3.to_hex(lg["transactionHash"]).lower()
        if bn not in block_times:
            block_times[bn] = _save_block(chain_id, w3.eth.get_block(bn))
        ce, created = ChainEvent.objects.get_or_create(
            chain_id=chain_id, tx_hash=tx_hash, log_index=li,
            defaults={"block_number": bn, "contract": contract, "event": event, "args": args})
        if not created:
            continue  # replay-safe
        txs_seen.setdefault(tx_hash, bn)
        ctx = handlers.EventCtx(contract=contract, event=event, args=args, block=bn, log_index=li, tx_hash=tx_hash,
                                at=block_times[bn], chain_event=ce)
        handlers.handle(ctx, pass_)
        n += 1
    for tx_hash, bn in txs_seen.items():
        _save_tx(chain_id, decoder, w3, tx_hash, bn, block_times[bn], pass_)
    return n


def _save_tx(chain_id, decoder, w3, tx_hash, bn, at, pass_):
    if ChainTx.objects.filter(tx_hash=tx_hash).exists():
        return
    tx = w3.eth.get_transaction(tx_hash)
    rc = w3.eth.get_transaction_receipt(tx_hash)
    contract, fn = decoder.function_of(tx)
    lbl_fn, lbl_args, records = pass_.labels.get(tx_hash, (fn, "", []))
    gas_used = int(rc["gasUsed"])
    price = int(rc.get("effectiveGasPrice") or tx.get("gasPrice") or 0)
    frm = tx["from"].lower()
    ChainTx.objects.create(
        tx_hash=tx_hash, chain_id=chain_id, from_address=frm, from_public_id=public_id(frm),
        to_address=(tx.get("to") or "").lower(), contract=contract or "", function=lbl_fn or fn,
        args_label=lbl_args, record_ids=records, block_number=bn, tx_index=int(rc["transactionIndex"]), at=at,
        status="Success" if int(rc["status"]) == 1 else "Reverted", gas_used=gas_used,
        effective_gas_price_wei=price, cost_wei=gas_used * price)


def resync(from_block: int | None = None) -> dict:
    dep = client.deployment()
    head = client.head_block()
    with transaction.atomic():
        cursor, _ = IndexerCursor.objects.select_for_update().get_or_create(
            chain_id=settings.CHAIN_ID,
            defaults={"title_registry_address": dep.address("TitleRegistry"), "last_block": dep.start_block - 1})
        _reset_cursor(cursor, dep, from_block)
    return {"from_block": dep.start_block if from_block is None else from_block, "head_block": head}
