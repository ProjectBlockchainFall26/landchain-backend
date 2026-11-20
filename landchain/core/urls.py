"""Routes for this app, mounted under /api/v1/ by landchain/api_urls.py."""
from django.urls import re_path

from . import views

urlpatterns = [
    re_path(r"^health/?$", views.HealthView.as_view()),  # /health
]
