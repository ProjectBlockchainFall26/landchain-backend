"""Routes for this app, mounted under /api/v1/ by landchain/api_urls.py."""
from django.urls import re_path

from . import views

urlpatterns = [
    re_path(r"^dev/demo-accounts/?$", views.DevDemoAccountsView.as_view()),  # /dev/demo-accounts
]
