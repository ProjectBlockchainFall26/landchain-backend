"""Routes for this app, mounted under /api/v1/ by landchain/api_urls.py."""
from django.urls import re_path

from . import views

urlpatterns = [
    re_path(r"^documents/?$", views.DocumentsView.as_view()),  # /documents
    re_path(r"^documents/(?P<sha256>0x[0-9a-fA-F]{64})/url/?$", views.DocumentsDetailUrlView.as_view()),  # /documents/{sha256}/url
    re_path(r"^parcels/(?P<parcel_id>[A-Za-z]{2}-[A-Za-z]{3}-\d{4})/documents/check/?$", views.ParcelsDetailDocumentsCheckView.as_view()),  # /parcels/{parcel_id}/documents/check
]
