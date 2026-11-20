from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Copy ABIs and deployments from ../landchain-contracts/shared into contracts/."

    def handle(self, *args, **options):
        # TODO(B2, Person B): web3 client, contract loader and encoding rules
        raise CommandError("Not built yet: task B2.")
