import json
import shutil
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from landchain.chain import contracts

FILES = ["deployments.local.json", "deployments.json", "demo-accounts.local.json"]


class Command(BaseCommand):
    help = "Copy ABIs and deployments from ../landchain-contracts/shared into contracts/ (task B2)."

    def add_arguments(self, parser):
        parser.add_argument("--from", dest="src", default=str(Path(settings.BASE_DIR).parent / "landchain-contracts"
                                                                   / "shared"))

    def handle(self, *args, **opts):
        src = Path(opts["src"]).expanduser().resolve()
        dst = Path(settings.CONTRACTS_DIR).resolve()
        if src == dst:
            raise CommandError("Source and destination are the same folder.")
        if not (src / "abi").is_dir():
            raise CommandError(f"{src}/abi not found. Run npm run setup:local in landchain-contracts first.")
        (dst / "abi").mkdir(parents=True, exist_ok=True)
        n = 0
        for name in contracts.NAMES:
            f = src / "abi" / f"{name}.json"
            if not f.exists() and name in contracts.OPTIONAL:
                continue
            if not f.exists():
                raise CommandError(f"Missing {f}. Run npm run contracts:compile in landchain-contracts.")
            shutil.copyfile(f, dst / "abi" / f.name)
            n += 1
        copied = []
        for name in FILES:
            f = src / name
            if f.exists():
                shutil.copyfile(f, dst / name)
                copied.append(name)
        contracts.clear_cache()
        deps = {}
        for name in ("deployments.local.json", "deployments.json"):
            if (dst / name).exists():
                deps.update(json.loads((dst / name).read_text()))
        self.stdout.write(self.style.SUCCESS(
            f"Synced {n} ABIs and {', '.join(copied) or 'no deployment files'} into {dst}. "
            f"Chains: {', '.join(deps) or 'none'}."))
