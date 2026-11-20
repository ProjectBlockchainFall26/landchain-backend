"""Routes for this app, mounted under /api/v1/ by landchain/api_urls.py."""
from django.urls import re_path

from . import views, views_activity

urlpatterns = [
    re_path(r"^activity/?$", views_activity.ActivityView.as_view()),  # /activity
    re_path(r"^admin/indexer/resync/?$", views.AdminIndexerResyncView.as_view()),  # /admin/indexer/resync
]
