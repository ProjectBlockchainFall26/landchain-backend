"""Routes for this app, mounted under /api/v1/ by landchain/api_urls.py."""
from django.urls import re_path

from . import admin_views, views

urlpatterns = [
    re_path(r"^admin/chain/roles/?$", admin_views.AdminChainRolesView.as_view()),  # /admin/chain/roles
    re_path(r"^admin/signers/?$", admin_views.AdminSignersView.as_view()),  # /admin/signers
    re_path(r"^chain/status/?$", views.ChainStatusView.as_view()),  # /chain/status
    re_path(r"^config/?$", views.ConfigView.as_view()),  # /config
    re_path(r"^chain/intents/(?P<id>[^/]+)/?$", views.ChainIntentsDetailView.as_view()),  # /chain/intents/{id}
    re_path(r"^chain/intents/(?P<id>[^/]+)/dev-sign/?$", views.ChainIntentsDetailDevSignView.as_view()),  # /chain/intents/{id}/dev-sign
    re_path(r"^chain/intents/(?P<id>[^/]+)/rejected-by-wallet/?$", views.ChainIntentsDetailRejectedByWalletView.as_view()),  # /chain/intents/{id}/rejected-by-wallet
    re_path(r"^chain/intents/(?P<id>[^/]+)/submitted/?$", views.ChainIntentsDetailSubmittedView.as_view()),  # /chain/intents/{id}/submitted
]
