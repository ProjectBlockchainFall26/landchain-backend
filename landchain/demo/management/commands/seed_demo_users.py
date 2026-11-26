from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from landchain.accounts import supabase_admin
from landchain.accounts.auth import dev_user_id
from landchain.accounts.models import Profile
from landchain.chain.contracts import demo_labels
from landchain.chain.encoding import public_id

# Seeded Ganache accounts (landchain-contracts scripts/seed.js), in account order.
ROLES_BY_INDEX = {0: ["registrar", "admin"], 1: ["id_officer"]}


def demo_email(name: str) -> str:
    first = name.split()[0].lower()
    return "registrar@demo.landchain.local" if name == "Lands Commission" else f"{first}@demo.landchain.local"


class Command(BaseCommand):
    help = ("Create the 8 demo people as Supabase users linked to their Ganache addresses (task A6). "
            "Without Supabase keys, creates the profiles only (sign in locally with X-Dev-User).")

    def handle(self, *args, **options):
        if settings.CHAIN_ID != 1337 or not settings.DEMO_MODE:
            raise CommandError("Demo users only exist on the local chain with DEMO_MODE=true.")
        labels = demo_labels()
        if not labels:
            raise CommandError("contracts/demo-accounts.local.json is missing. Run npm run setup:local in "
                               "landchain-contracts, then python manage.py sync_contracts.")
        if supabase_admin.configured() and not settings.DEMO_PASSWORD:
            raise CommandError("Set DEMO_PASSWORD.")
        for i, person in enumerate(labels):
            email, name, address = demo_email(person["name"]), person["name"], person["address"].lower()
            roles = ROLES_BY_INDEX.get(i, [])
            user = supabase_admin.ensure_user(email, settings.DEMO_PASSWORD, name)
            uid = user.id if user is not None else dev_user_id(email)
            Profile.objects.filter(wallet_address=address).exclude(supabase_user_id=uid).update(
                wallet_address=None, public_id=None)
            p, _ = Profile.objects.update_or_create(supabase_user_id=uid, defaults={
                "email": email, "full_name": name, "wallet_address": address, "public_id": public_id(address),
                "wallet_linked_at": timezone.now(), "roles": roles, "is_demo": True})
            supabase_admin.sync_roles(p.supabase_user_id, roles)
            self.stdout.write(f"{name:<17} {email:<34} {address} {p.public_id} {','.join(roles) or 'citizen'}")
        self.stdout.write(self.style.SUCCESS(
            f"Seeded {len(labels)} demo users" + (" in Supabase." if supabase_admin.configured() else
                                                   " (profiles only: use X-Dev-User: <email>).")))
