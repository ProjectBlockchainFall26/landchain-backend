from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Print balance, nonce and on-chain role of each signer wallet."

    def handle(self, *args, **options):
        # TODO(B7, Person B): Admin chain tools: role wallets and signer health
        raise CommandError("Not built yet: task B7.")
