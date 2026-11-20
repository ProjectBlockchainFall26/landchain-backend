from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("api/v1/", include("landchain.api_urls")),
    # TODO(D1): /api/v1/schema/ and /api/v1/docs/ with drf-spectacular
]
