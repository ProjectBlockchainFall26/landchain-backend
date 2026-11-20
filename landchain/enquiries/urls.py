"""Routes for this app, mounted under /api/v1/ by landchain/api_urls.py."""
from django.urls import re_path

from . import views

urlpatterns = [
    re_path(r"^me/enquiries/?$", views.MeEnquiriesView.as_view()),  # /me/enquiries
    re_path(r"^enquiries/(?P<id>[^/]+)/?$", views.EnquiriesDetailView.as_view()),  # /enquiries/{id}
    re_path(r"^parcels/(?P<parcel_id>[A-Za-z]{2}-[A-Za-z]{3}-\d{4})/enquiries/?$", views.ParcelsDetailEnquiriesView.as_view()),  # /parcels/{parcel_id}/enquiries
]
