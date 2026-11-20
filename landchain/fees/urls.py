"""Routes for this app, mounted under /api/v1/ by landchain/api_urls.py."""
from django.urls import re_path

from . import views, views_receipt

urlpatterns = [
    re_path(r"^fees/estimate/?$", views.FeesEstimateView.as_view()),  # /fees/estimate
    re_path(r"^fees/schedule/?$", views.FeesScheduleView.as_view()),  # /fees/schedule
    re_path(r"^parcels/(?P<parcel_id>[A-Za-z]{2}-[A-Za-z]{3}-\d{4})/payments/?$", views.ParcelsDetailPaymentsView.as_view()),  # /parcels/{parcel_id}/payments
    re_path(r"^parcels/(?P<parcel_id>[A-Za-z]{2}-[A-Za-z]{3}-\d{4})/receipt/?$", views_receipt.ParcelsDetailReceiptView.as_view()),  # /parcels/{parcel_id}/receipt
]
