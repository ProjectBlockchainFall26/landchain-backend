"""Scaffold helper: lets every route exist before it is built. Delete once no view imports it."""
from rest_framework.response import Response


def not_implemented(task: str, request) -> Response:
    return Response(
        {"error": {"code": "NOT_IMPLEMENTED",
                   "message": f"{request.method} {request.path} is not built yet. Owner task: {task}.",
                   "task": task}},
        status=501,
    )
