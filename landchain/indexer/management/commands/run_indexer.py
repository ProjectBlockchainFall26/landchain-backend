import time

from django.conf import settings
from django.core.management.base import BaseCommand

from landchain.core.errors import ChainUnavailable


class Command(BaseCommand):
    help = "Follow the four LandChain contracts' events into Postgres (task C3). --once for a single pass."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")
        parser.add_argument("--resync", action="store_true", help="wipe the projection and start from startBlock")
        parser.add_argument("--interval", type=float, default=None)

    def handle(self, *args, **opts):
        from landchain.chain.service import watch_intents
        from landchain.indexer.runner import resync, run_once
        if opts["resync"]:
            self.stdout.write(str(resync()))
        interval = opts["interval"] or settings.INDEXER_INTERVAL_S
        last_error = None
        while True:
            try:
                out = run_once()
                watch_intents()
                if out.get("events") or opts["once"]:
                    self.stdout.write(f"indexed blocks {out.get('from')}..{out.get('to')}: {out.get('events', 0)} "
                                      f"events, {out.get('confirmed', 0)} intents confirmed")
                last_error = None
            except ChainUnavailable as e:
                if e.message != last_error:
                    self.stderr.write(e.message)
                last_error = e.message
                if opts["once"]:
                    raise
            if opts["once"]:
                return
            time.sleep(interval)
