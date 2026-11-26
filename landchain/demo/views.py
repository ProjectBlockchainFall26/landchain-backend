"""GET /dev/demo-accounts (task A6, spec 9.1) and the local vault file link (development only)."""
from django.conf import settings
from django.core import signing
from django.http import Http404, HttpResponse
from rest_framework.response import Response
from rest_framework.views import APIView

from landchain.accounts.models import Profile
from landchain.core.permissions import Public
from landchain.registry.models import ChainIdentity


class DevDemoAccountsView(APIView):
    """GET /api/v1/dev/demo-accounts [Public · local chain only]. 404 unless CHAIN_ID=1337 and DEMO_MODE=true."""

    permission_classes = [Public]

    def get(self, request, *args, **kwargs):
        if settings.CHAIN_ID != 1337 or not settings.DEMO_MODE:
            raise Http404("Not found.")
        people = list(Profile.objects.filter(is_demo=True).order_by("created_at", "email"))
        ids = {c.address: c for c in ChainIdentity.objects.filter(address__in=[p.wallet_address for p in people])}
        order = {"registrar@demo.landchain.local": 0, "abena@demo.landchain.local": 1}
        people.sort(key=lambda p: (order.get(p.email, 2), p.created_at))
        accounts = []
        for p in people:
            row = {"name": p.full_name, "email": p.email, "kind": p.kind, "roles": p.role_labels,
                   "public_id": p.public_id, "address": p.wallet_address}
            if not p.is_officer:
                ci = ids.get(p.wallet_address)
                row["identity"] = ci.status_name if ci else "none"
                if ci and not ci.citizen and ci.status:
                    row["citizenship"] = "non-citizen"
            accounts.append(row)
        return Response({"password_hint": "set by DEMO_PASSWORD", "accounts": accounts,
                         "dev_header": "X-Dev-User" if (settings.DEBUG and settings.DEV_AUTH) else None})


class DevVaultFileView(APIView):
    """GET /api/v1/dev/vault/<token>: serves a local-vault file behind a 60 s signed link (no Supabase)."""

    permission_classes = [Public]
    authentication_classes = []

    def get(self, request, token, *args, **kwargs):
        from landchain.documents import storage
        if storage.using_supabase():
            raise Http404("Not found.")
        try:
            data, name, mime = storage.read_signed(token)
        except (signing.BadSignature, FileNotFoundError):
            raise Http404("This link expired. Open the file again.") from None
        resp = HttpResponse(data, content_type=mime)
        resp["Content-Disposition"] = f'inline; filename="{name}"'
        resp["Cache-Control"] = "no-store"
        return resp
