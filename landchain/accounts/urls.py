"""Routes for this app, mounted under /api/v1/ by landchain/api_urls.py."""
from django.urls import re_path

from . import admin_views, views

urlpatterns = [
    re_path(r"^admin/officers/?$", admin_views.AdminOfficersView.as_view()),  # /admin/officers
    re_path(r"^auth/wallet/nonce/?$", views.AuthWalletNonceView.as_view()),  # /auth/wallet/nonce
    re_path(r"^auth/wallet/verify/?$", views.AuthWalletVerifyView.as_view()),  # /auth/wallet/verify
    re_path(r"^me/?$", views.MeView.as_view()),  # /me
    re_path(r"^admin/officers/(?P<user_id>[0-9a-fA-F-]{36})/?$", admin_views.AdminOfficersDetailView.as_view()),  # /admin/officers/{user_id}
]
