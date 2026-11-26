"""web3.py client built from RPC_URL, plus contract objects. Task B2.

    from landchain.chain import client
    w3 = client.w3()
    titles = client.contract("TitleRegistry")
    titles.functions.getParcel(2).call()

Raises ChainUnavailable (503) with the frontend's wording when the RPC can't be reached or the contracts
aren't deployed at the configured addresses.
"""
from __future__ import annotations

import threading

from django.conf import settings
from web3 import Web3
from web3.contract import Contract

from landchain.core.errors import ChainUnavailable

from . import contracts as registry

_local = threading.local()


def w3() -> Web3:
    inst = getattr(_local, "w3", None)
    if inst is None or getattr(_local, "url", None) != settings.RPC_URL:
        inst = Web3(Web3.HTTPProvider(settings.RPC_URL, request_kwargs={"timeout": 15}))
        _local.w3, _local.url = inst, settings.RPC_URL
    return inst


def unreachable_message() -> str:
    return f"Can't reach {settings.RPC_URL_PUBLIC or settings.RPC_URL}. Is the chain running?"


MISSING_CONTRACTS = ("This chain doesn't have the current LandChain contracts. "
                     "Run npm run setup:all in landchain-contracts.")


def deployment():
    try:
        return registry.deployment()
    except registry.ContractsMissing as e:
        raise ChainUnavailable(str(e)) from e


def contract(name: str) -> Contract:
    dep = deployment()
    return w3().eth.contract(address=Web3.to_checksum_address(dep.address(name)), abi=registry.abi(name))


def all_contracts() -> dict[str, Contract]:
    return {n: contract(n) for n in registry.NAMES}


def head_block() -> int:
    try:
        return int(w3().eth.block_number)
    except Exception as e:  # requests ConnectionError, timeouts, etc.
        raise ChainUnavailable(unreachable_message()) from e


def chain_id_onchain() -> int:
    try:
        return int(w3().eth.chain_id)
    except Exception as e:
        raise ChainUnavailable(unreachable_message()) from e


def contracts_match() -> bool:
    """Code exists at every configured address."""
    dep = deployment()
    eth = w3().eth
    try:
        return all(len(eth.get_code(Web3.to_checksum_address(a))) > 0 for a in dep.addresses.values())
    except Exception as e:
        raise ChainUnavailable(unreachable_message()) from e


def checksum(address: str) -> str:
    return Web3.to_checksum_address(address)
