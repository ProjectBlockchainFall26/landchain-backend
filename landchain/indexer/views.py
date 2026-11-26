"""POST /admin/indexer/resync (task C4, spec 9.13)."""
from __future__ import annotations

from rest_framework.response import Response
from rest_framework.views import APIView

from landchain.core.errors import Validation
from landchain.core.ids import new_id
from landchain.core.permissions import IsAdmin


class AdminIndexerResyncView(APIView):
    """POST /api/v1/admin/indexer/resync [IsAdmin]: wipe the projection and re-index from startBlock."""

    permission_classes = [IsAdmin]

    def post(self, request, *args, **kwargs):
        from .runner import resync
        from .tasks import indexer_tick
        fb = request.data.get("from_block")
        if fb is not None:
            try:
                fb = int(fb)
                if fb < 0:
                    raise ValueError
            except (TypeError, ValueError):
                raise Validation("from_block is a block number", field_errors={"from_block": ["A block number"]}) \
                    from None
        out = resync(fb)
        job = indexer_tick.delay()
        return Response({"job_id": getattr(job, "id", None) or new_id("job"), **out}, status=202)
