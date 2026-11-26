from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Print balance, nonce and on-chain role of each signer wallet (task B7)."

    def handle(self, *args, **options):
        from landchain.chain.admin_views import signer_rows
        for r in signer_rows():
            ok = r.get("has_role_on_chain") and not r.get("low_balance") and not r.get("error")
            style = self.style.SUCCESS if ok else self.style.ERROR
            self.stdout.write(style(
                f"{r['role']:<11} {r['address'] or '-':<44} balance={r['balance_eth']} nonce={r['pending_nonce']} "
                f"role_on_chain={r['has_role_on_chain']} queue={r['queue_depth']} {r.get('error', '')}"))
