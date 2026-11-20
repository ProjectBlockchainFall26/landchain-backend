"""Routes for this app, mounted under /api/v1/ by landchain/api_urls.py."""
from django.urls import re_path

from . import views_applications, views_identity, views_parcels, views_review, views_transfers

urlpatterns = [
    re_path(r"^applications/?$", views_applications.ApplicationsView.as_view()),  # /applications
    re_path(r"^identities/?$", views_identity.IdentitiesView.as_view()),  # /identities
    re_path(r"^identities/lookup/?$", views_identity.IdentitiesLookupView.as_view()),  # /identities/lookup
    re_path(r"^identity/submit/?$", views_identity.IdentitySubmitView.as_view()),  # /identity/submit
    re_path(r"^me/parcels/?$", views_parcels.MeParcelsView.as_view()),  # /me/parcels
    re_path(r"^parcels/?$", views_parcels.ParcelsView.as_view()),  # /parcels
    re_path(r"^parcels/boundary-check/?$", views_parcels.ParcelsBoundaryCheckView.as_view()),  # /parcels/boundary-check
    re_path(r"^parcels/next-id/?$", views_parcels.ParcelsNextIdView.as_view()),  # /parcels/next-id
    re_path(r"^parcels/search/?$", views_parcels.ParcelsSearchView.as_view()),  # /parcels/search
    re_path(r"^review/counts/?$", views_review.ReviewCountsView.as_view()),  # /review/counts
    re_path(r"^review/queue/?$", views_review.ReviewQueueView.as_view()),  # /review/queue
    re_path(r"^stats/?$", views_parcels.StatsView.as_view()),  # /stats
    re_path(r"^transfers/?$", views_transfers.TransfersView.as_view()),  # /transfers
    re_path(r"^applications/(?P<id>[^/]+)/?$", views_applications.ApplicationsDetailView.as_view()),  # /applications/{id}
    re_path(r"^applications/(?P<id>[^/]+)/approve/?$", views_applications.ApplicationsDetailApproveView.as_view()),  # /applications/{id}/approve
    re_path(r"^applications/(?P<id>[^/]+)/reject/?$", views_applications.ApplicationsDetailRejectView.as_view()),  # /applications/{id}/reject
    re_path(r"^identities/(?P<public_id>GH-[0-9a-fA-F]{8})/reject/?$", views_identity.IdentitiesDetailRejectView.as_view()),  # /identities/{public_id}/reject
    re_path(r"^identities/(?P<public_id>GH-[0-9a-fA-F]{8})/verify/?$", views_identity.IdentitiesDetailVerifyView.as_view()),  # /identities/{public_id}/verify
    re_path(r"^parcels/(?P<parcel_id>[A-Za-z]{2}-[A-Za-z]{3}-\d{4})/?$", views_parcels.ParcelsDetailView.as_view()),  # /parcels/{parcel_id}
    re_path(r"^parcels/(?P<parcel_id>[A-Za-z]{2}-[A-Za-z]{3}-\d{4})/history/?$", views_parcels.ParcelsDetailHistoryView.as_view()),  # /parcels/{parcel_id}/history
    re_path(r"^transfers/(?P<id>[^/]+)/?$", views_transfers.TransfersDetailView.as_view()),  # /transfers/{id}
    re_path(r"^transfers/(?P<id>[^/]+)/approve/?$", views_transfers.TransfersDetailApproveView.as_view()),  # /transfers/{id}/approve
    re_path(r"^transfers/(?P<id>[^/]+)/cancel/?$", views_transfers.TransfersDetailCancelView.as_view()),  # /transfers/{id}/cancel
    re_path(r"^transfers/(?P<id>[^/]+)/reject/?$", views_transfers.TransfersDetailRejectView.as_view()),  # /transfers/{id}/reject
]
