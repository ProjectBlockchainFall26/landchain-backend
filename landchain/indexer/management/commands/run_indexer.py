from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Follow contract events into Postgres (spec 6.5)."

    def handle(self, *args, **options):
        # TODO(C3, Person C): `run_indexer`: follow contract events into Postgres
        raise CommandError("Not built yet: task C3.")
