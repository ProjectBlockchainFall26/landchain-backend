"""Routes for this app, mounted under /api/v1/ by landchain/api_urls.py."""
from django.urls import re_path

from . import views

urlpatterns = [
    re_path(r"^me/notifications/?$", views.MeNotificationsView.as_view()),  # /me/notifications
    re_path(r"^me/notifications/read/?$", views.MeNotificationsReadView.as_view()),  # /me/notifications/read
]
