"""eth_call simulation and revert reason extraction (task B3, spec 10.1). Port of revertReason() in client.ts."""
from __future__ import annotations

import re

from eth_abi import decode as abi_decode
from web3.exceptions import ContractCustomError, ContractLogicError, ContractPanicError, Web3RPCError

from landchain.core.errors import ChainRevert, ChainUnavailable

from . import client

_PATTERNS = [
    re.compile(r"reverted with reason string '([^']+)'", re.I),
    re.compile(r"VM Exception while processing transaction: revert\s+([^'\"\n]+)", re.I),
    re.compile(r"execution reverted:\s*([^'\"\n]+)", re.I),
]

# OpenZeppelin 5 custom errors (4-byte selectors) mapped to sentences.
CUSTOM_ERRORS = {
    "AccessControlUnauthorizedAccount": "You don't have the Lands Commission role for this.",
    "AccessControlBadConfirmation": "Role change not confirmed.",
    "ERC721NonexistentToken": "Title not found",
    "ERC721InsufficientApproval": "Titles move only through a registrar-approved transfer",
    "ERC721IncorrectOwner": "Titles move only through a registrar-approved transfer",
}


def reason_from_text(text: str) -> str | None:
    for p in _PATTERNS:
        m = p.search(text or "")
        if m:
            r = m.group(1).strip().rstrip("'").strip()
            if r and not r.startswith("0x"):
                return r
    if re.search(r"user (rejected|denied)", text or "", re.I):
        return "You cancelled the transaction in your wallet"
    return None


def _decode_error_data(data: str | None) -> str | None:
    if not data or not isinstance(data, str) or not data.startswith("0x") or len(data) < 10:
        return None
    sel, body = data[:10], bytes.fromhex(data[10:])
    if sel == "0x08c379a0":  # Error(string)
        try:
            return abi_decode(["string"], body)[0]
        except Exception:
            return None
    from eth_utils import keccak

    from . import contracts as reg
    for name in reg.NAMES:
        try:
            for item in reg.abi(name):
                if item.get("type") != "error":
                    continue
                sig = f"{item['name']}({','.join(i['type'] for i in item['inputs'])})"
                if "0x" + keccak(text=sig)[:4].hex() == sel:
                    return CUSTOM_ERRORS.get(item["name"], item["name"])
        except Exception:
            continue
    return None


def revert_reason(exc: BaseException) -> str:
    texts: list[str] = []
    rpc = getattr(exc, "rpc_response", None) or {}
    err = rpc.get("error") if isinstance(rpc, dict) else None
    if isinstance(err, dict):
        d = _decode_error_data(err.get("data") if isinstance(err.get("data"), str) else None)
        if d:
            return d
        texts.append(str(err.get("message", "")))
    data = getattr(exc, "data", None)
    decoded = _decode_error_data(data if isinstance(data, str) else None)
    if decoded:
        return decoded
    for a in getattr(exc, "args", ()):
        if isinstance(a, dict):
            texts += [str(a.get("message", "")), str(a.get("data", ""))]
            d = _decode_error_data(a.get("data") if isinstance(a.get("data"), str) else None)
            if d:
                return d
        else:
            texts.append(str(a))
    texts.append(str(getattr(exc, "message", "") or ""))
    texts.append(str(exc))
    for t in texts:
        m = re.search(r"0x08c379a0[0-9a-fA-F]+", t)
        if m:
            d = _decode_error_data(m.group(0))
            if d:
                return d
    for t in texts:
        r = reason_from_text(t)
        if r:
            return r
    for t in texts:
        t = t.strip()
        if t and not t.startswith("0x") and t != "None":
            return t.removeprefix("execution reverted").strip(": ") or "Transaction failed"
    return "Transaction failed"


def is_connection_error(exc: BaseException) -> bool:
    name = type(exc).__name__
    return any(k in name for k in ("ConnectionError", "Timeout", "MaxRetry", "NewConnection")) \
        or "Connection refused" in str(exc)


REVERTS = (ContractLogicError, ContractCustomError, ContractPanicError)


def _is_revert_rpc(e: BaseException) -> bool:
    text = str(e)
    return "revert" in text.lower() or "0x08c379a0" in text


def simulate(fn, from_address: str):
    """Run fn.call({'from': ...}). Returns the call's return value or raises ChainRevert(reason)."""
    try:
        return fn.call({"from": client.checksum(from_address)})
    except REVERTS as e:
        raise ChainRevert(revert_reason(e)) from e
    except (Web3RPCError, ValueError) as e:  # Ganache: Web3RPCError({'message': 'VM Exception ... revert ...'})
        if _is_revert_rpc(e) or isinstance(e, ValueError):
            raise ChainRevert(revert_reason(e)) from e
        raise
    except Exception as e:
        if is_connection_error(e):
            raise ChainUnavailable(client.unreachable_message()) from e
        raise


def estimate_gas(fn, from_address: str) -> int:
    try:
        return int(fn.estimate_gas({"from": client.checksum(from_address)}) * 12 // 10)
    except REVERTS as e:
        raise ChainRevert(revert_reason(e)) from e
    except (Web3RPCError, ValueError) as e:
        if _is_revert_rpc(e) or isinstance(e, ValueError):
            raise ChainRevert(revert_reason(e)) from e
        raise
    except Exception as e:
        if is_connection_error(e):
            raise ChainUnavailable(client.unreachable_message()) from e
        raise
