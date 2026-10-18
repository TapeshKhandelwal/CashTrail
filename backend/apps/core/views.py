from django.db import connection
from django.http import JsonResponse
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@extend_schema(
    responses=inline_serializer(
        "Health",
        {"status": serializers.CharField(), "database": serializers.CharField()},
    ),
)
@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def health(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return Response({"status": "ok", "database": "ok"})


def _error(code: str, message: str, status: int) -> JsonResponse:
    return JsonResponse({"error": {"code": code, "message": message, "details": {}}}, status=status)


def bad_request(request, exception=None):
    return _error("BAD_REQUEST", "The request could not be processed.", 400)


def permission_denied(request, exception=None):
    return _error("PERMISSION_DENIED", "You are not allowed to perform this action.", 403)


def csrf_failure(request, reason=""):
    return _error("CSRF_FAILED", "The CSRF check failed. Reload the page and try again.", 403)


def not_found(request, exception=None):
    return _error("NOT_FOUND", "Not found.", 404)


def server_error(request):
    return _error("INTERNAL_ERROR", "Something went wrong on our side. Please try again.", 500)
