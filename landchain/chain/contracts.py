"""ABIs and addresses. Task B2, spec 6.1.

Reads CONTRACTS_DIR (written by `manage.py sync_contracts`, or point it straight at
landchain-contracts/shared): abi/<Name>.json and deployments.local.json keyed by chain id.
The four *_ADDRESS variables and START_BLOCK override the file (useful on Sepolia).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from django.conf import settings

NAMES = ("LandAccessControl", "IdentityRegistry", "TitleRegistry", "FeeLedger")
ENV_ADDRESS = {"LandAccessControl": "LAND_ACCESS_CONTROL_ADDRESS", "IdentityRegistry": "IDENTITY_REGISTRY_ADDRESS",
               "TitleRegistry": "TITLE_REGISTRY_ADDRESS", "FeeLedger": "FEE_LEDGER_ADDRESS"}


class ContractsMissing(Exception):
    pass


@dataclass(frozen=True)
class Deployment:
    chain_id: int
    network: str
    start_block: int
    deployed_at: str | None
    addresses: dict  # name -> lowercase address

    def address(self, name: str) -> str:
        return self.addresses[name]

    def name_of(self, address: str) -> str | None:
        address = (address or "").lower()
        for n, a in self.addresses.items():
            if a == address:
                return n
        return None


def contracts_dir() -> Path:
    return Path(settings.CONTRACTS_DIR)


def _read_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=8)
def _abi_cached(directory: str, name: str) -> tuple:
    path = Path(directory) / "abi" / f"{name}.json"
    if not path.exists():
        raise ContractsMissing(f"Missing ABI {path}. Run python manage.py sync_contracts.")
    data = _read_json(path)
    abi = data["abi"] if isinstance(data, dict) else data
    return tuple(json.dumps(x, sort_keys=True) for x in abi)


def abi(name: str) -> list[dict]:
    return [json.loads(x) for x in _abi_cached(str(contracts_dir()), name)]


def _deployments_file() -> Path:
    return contracts_dir() / "deployments.local.json"


def deployment(chain_id: int | None = None) -> Deployment:
    chain_id = chain_id or settings.CHAIN_ID
    entry: dict = {}
    path = _deployments_file()
    if path.exists():
        entry = _read_json(path).get(str(chain_id)) or {}
    addrs = {n: (os.environ.get(ENV_ADDRESS[n]) or (entry.get("contracts") or {}).get(n) or "").lower()
             for n in NAMES}
    if not all(addrs.values()):
        raise ContractsMissing(
            f"No LandChain deployment for chain {chain_id}. Run npm run setup:all in landchain-contracts, "
            "then python manage.py sync_contracts.")
    start = int(os.environ.get("START_BLOCK") or entry.get("startBlock") or 0)
    return Deployment(chain_id=chain_id, network=entry.get("network", "unknown"), start_block=start,
                      deployed_at=entry.get("deployedAt"), addresses=addrs)


def demo_labels() -> list[dict]:
    """Seeded demo people [{address, name}] written by the contracts' seed script (local chain only)."""
    path = contracts_dir() / "demo-accounts.local.json"
    if not path.exists():
        return []
    return [{"address": x["address"].lower(), "name": x["name"]} for x in _read_json(path)]


def clear_cache():
    _abi_cached.cache_clear()
