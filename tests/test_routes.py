"""Every route in the spec must exist and accept its method (no 404 from the router, no 405)."""
import pytest
from django.urls import Resolver404, resolve

ROUTES = [
    ("DELETE", "/api/v1/admin/officers/8d0f6c1e-5b3a-4f7e-9a51-2c1d0e7b9f33"),
    ("GET", "/api/v1/activity"),
    ("GET", "/api/v1/admin/officers"),
    ("GET", "/api/v1/admin/signers"),
    ("GET", "/api/v1/applications"),
    ("GET", "/api/v1/applications/APP-7"),
    ("GET", "/api/v1/chain/intents/txi_01JD3K8W5Q9Y2M7T4R6V1B0C3N"),
    ("GET", "/api/v1/chain/status"),
    ("GET", "/api/v1/config"),
    ("GET", "/api/v1/dev/demo-accounts"),
    ("GET", "/api/v1/documents/0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/url"),
    ("GET", "/api/v1/fees/estimate"),
    ("GET", "/api/v1/fees/schedule"),
    ("GET", "/api/v1/health"),
    ("GET", "/api/v1/identities"),
    ("GET", "/api/v1/identities/lookup"),
    ("GET", "/api/v1/me"),
    ("GET", "/api/v1/me/enquiries"),
    ("GET", "/api/v1/me/notifications"),
    ("GET", "/api/v1/me/parcels"),
    ("GET", "/api/v1/parcels"),
    ("GET", "/api/v1/parcels/next-id"),
    ("GET", "/api/v1/parcels/search"),
    ("GET", "/api/v1/parcels/GA-BRK-0002"),
    ("GET", "/api/v1/parcels/GA-BRK-0002/history"),
    ("GET", "/api/v1/parcels/GA-BRK-0002/payments"),
    ("GET", "/api/v1/parcels/GA-BRK-0002/receipt"),
    ("GET", "/api/v1/review/counts"),
    ("GET", "/api/v1/review/queue"),
    ("GET", "/api/v1/stats"),
    ("GET", "/api/v1/transfers"),
    ("GET", "/api/v1/transfers/TRF-3"),
    ("PATCH", "/api/v1/enquiries/enq_01JD3K8W5Q9Y2M7T4R6V1B0C3N"),
    ("PATCH", "/api/v1/me"),
    ("POST", "/api/v1/admin/chain/roles"),
    ("POST", "/api/v1/admin/indexer/resync"),
    ("POST", "/api/v1/admin/officers"),
    ("POST", "/api/v1/applications"),
    ("POST", "/api/v1/applications/APP-7/approve"),
    ("POST", "/api/v1/applications/APP-7/reject"),
    ("POST", "/api/v1/auth/wallet/nonce"),
    ("POST", "/api/v1/auth/wallet/verify"),
    ("POST", "/api/v1/chain/intents/txi_01JD3K8W5Q9Y2M7T4R6V1B0C3N/dev-sign"),
    ("POST", "/api/v1/chain/intents/txi_01JD3K8W5Q9Y2M7T4R6V1B0C3N/rejected-by-wallet"),
    ("POST", "/api/v1/chain/intents/txi_01JD3K8W5Q9Y2M7T4R6V1B0C3N/submitted"),
    ("POST", "/api/v1/documents"),
    ("POST", "/api/v1/identities/GH-7d4e894d/reject"),
    ("POST", "/api/v1/identities/GH-7d4e894d/verify"),
    ("POST", "/api/v1/identity/submit"),
    ("POST", "/api/v1/me/notifications/read"),
    ("POST", "/api/v1/parcels/boundary-check"),
    ("POST", "/api/v1/parcels/GA-BRK-0002/documents/check"),
    ("POST", "/api/v1/parcels/GA-BRK-0002/enquiries"),
    ("POST", "/api/v1/parcels/GA-BRK-0002/payments"),
    ("POST", "/api/v1/transfers"),
    ("POST", "/api/v1/transfers/TRF-3/approve"),
    ("POST", "/api/v1/transfers/TRF-3/cancel"),
    ("POST", "/api/v1/transfers/TRF-3/reject"),
]


@pytest.mark.parametrize("method,url", ROUTES)
def test_route_exists(method, url):
    try:
        match = resolve(url)
    except Resolver404:
        pytest.fail(f"{method} {url} is not routed")
    view = match.func.view_class
    assert hasattr(view, method.lower()), f"{method} not allowed on {url}"


def test_no_stub_left():
    """Every view is built: nothing answers 501 NOT_IMPLEMENTED any more."""
    import pathlib
    root = pathlib.Path(__file__).resolve().parent.parent / "landchain"
    offenders = [str(p) for p in root.rglob("*.py") if "not_implemented(" in p.read_text()]
    assert offenders == []
