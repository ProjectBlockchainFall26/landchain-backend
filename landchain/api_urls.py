"""Every API route, mounted at /api/v1/. Each app owns its own urls.py."""
from django.urls import include, path

urlpatterns = [
    path("", include("landchain.core.urls")),
    path("", include("landchain.accounts.urls")),
    path("", include("landchain.chain.urls")),
    path("", include("landchain.registry.urls")),   # before fees/enquiries/documents: /parcels/... literals
    path("", include("landchain.documents.urls")),
    path("", include("landchain.fees.urls")),
    path("", include("landchain.enquiries.urls")),
    path("", include("landchain.notifications.urls")),
    path("", include("landchain.indexer.urls")),
    path("", include("landchain.demo.urls")),
]
