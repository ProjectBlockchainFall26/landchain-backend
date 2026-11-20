"""Stub views. Each returns 501 until its task is built. Owners are in the docstrings."""
from rest_framework.views import APIView

from landchain.core.stubs import not_implemented


class MeParcelsView(APIView):
    """
    GET /api/v1/me/parcels  [IsSignedIn]
        Task C5 (Person C): Parcel and map reads (+ `/stats`, `/me/parcels`)
        Spec: docs/api-spec.md section 9.2 · Postman: 'GET /me/parcels'
        Parcels whose current owner is me (My Parcels page), plus my pending and rejected
    applications.
    """

    def get(self, request, *args, **kwargs):
        # TODO(C5): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("C5", request)


class ParcelsView(APIView):
    """
    GET /api/v1/parcels  [Public]
        Task C5 (Person C): Parcel and map reads (+ `/stats`, `/me/parcels`)
        Spec: docs/api-spec.md section 9.5 · Postman: 'GET /parcels'
        Map and Verify list. Current records only. Rejected parcels excluded unless asked.
    """

    def get(self, request, *args, **kwargs):
        # TODO(C5): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("C5", request)


class ParcelsSearchView(APIView):
    """
    GET /api/v1/parcels/search  [Public]
        Task C5 (Person C): Parcel and map reads (+ `/stats`, `/me/parcels`)
        Spec: docs/api-spec.md section 9.5 · Postman: 'GET /parcels/search'
        Map search box: "Parcel ID, owner ID or token #". Exact match first, then contains.
    """

    def get(self, request, *args, **kwargs):
        # TODO(C5): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("C5", request)


class ParcelsDetailView(APIView):
    """
    GET /api/v1/parcels/{parcel_id}  [Public (privacy-filtered)]
        Task C5 (Person C): Parcel and map reads (+ `/stats`, `/me/parcels`)
        Spec: docs/api-spec.md section 9.5 · Postman: 'GET /parcels/{parcel_id}'
        Title record. Case-insensitive parcel ID. Resolves to the latest record; ?record_id=
    fetches an older one.
    """

    def get(self, request, *args, **kwargs):
        # TODO(C5): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("C5", request)


class ParcelsDetailHistoryView(APIView):
    """
    GET /api/v1/parcels/{parcel_id}/history  [Public]
        Task C5 (Person C): Parcel and map reads (+ `/stats`, `/me/parcels`)
        Spec: docs/api-spec.md section 9.5 · Postman: 'GET /parcels/{parcel_id}/history'
        On-chain history, oldest first (block order).
    """

    def get(self, request, *args, **kwargs):
        # TODO(C5): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("C5", request)


class ParcelsNextIdView(APIView):
    """
    GET /api/v1/parcels/next-id  [Public]
        Task C5 (Person C): Parcel and map reads (+ `/stats`, `/me/parcels`)
        Spec: docs/api-spec.md section 9.5 · Postman: 'GET /parcels/next-id'
        Suggests the next free parcel ID (Register page placeholder; today it counts up from
    15).
    """

    def get(self, request, *args, **kwargs):
        # TODO(C5): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("C5", request)


class ParcelsBoundaryCheckView(APIView):
    """
    POST /api/v1/parcels/boundary-check  [Public]
        Task C6 (Person C): Geometry: `geo.py` + `POST /parcels/boundary-check`
        Spec: docs/api-spec.md section 9.5 · Postman: 'POST /parcels/boundary-check'
        Live check while drawing: area, plots, overlap, Ghana box, duplicate boundary. Replaces
    validateBoundary and areaAcres.
    """

    def post(self, request, *args, **kwargs):
        # TODO(C6): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("C6", request)


class StatsView(APIView):
    """
    GET /api/v1/stats  [Public]
        Task C5 (Person C): Parcel and map reads (+ `/stats`, `/me/parcels`)
        Spec: docs/api-spec.md section 9.5 · Postman: 'GET /stats'
        "Register snapshot" card and map filter counts.
    """

    def get(self, request, *args, **kwargs):
        # TODO(C5): implement. Request/response bodies are in the spec and the Postman example.
        return not_implemented("C5", request)

