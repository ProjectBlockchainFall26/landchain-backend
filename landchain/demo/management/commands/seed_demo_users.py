from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create the 8 demo people as Supabase users linked to Ganache addresses."

    def handle(self, *args, **options):
        # TODO(A6, Person A): Demo users: `seed_demo_users` + `/dev/demo-accounts`
        raise CommandError("Not built yet: task A6.")
