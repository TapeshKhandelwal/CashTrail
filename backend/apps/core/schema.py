"""OpenAPI helpers: one Swagger tag per domain, and the shared error envelope."""

from drf_spectacular.openapi import AutoSchema
from drf_spectacular.utils import OpenApiResponse
from rest_framework import serializers

from .api_tags import TAG_BY_SEGMENT


class DomainAutoSchema(AutoSchema):
    """Tags each operation with its domain, so Swagger shows one section per domain."""

    def get_tags(self) -> list[str]:
        segment = self.path.removeprefix("/api/").split("/", 1)[0]
        return [TAG_BY_SEGMENT.get(segment, *super().get_tags())]


_DESCRIPTIONS = {
    400: "Malformed request or field validation failed.",
    401: "Missing or invalid access token.",
    403: "Authenticated but not allowed.",
    404: "Not found or outside your scope.",
    409: "Conflict with the record's current state, a duplicate, or a locked record.",
    422: "The request breaks a business rule.",
    429: "Too many requests.",
    502: "The payment gateway could not be reached.",
}


class ErrorBodySerializer(serializers.Serializer):
    code = serializers.CharField()
    message = serializers.CharField()
    details = serializers.DictField()


class ErrorResponseSerializer(serializers.Serializer):
    error = ErrorBodySerializer()


def error_responses(*status_codes: int) -> dict[int, OpenApiResponse]:
    """`responses={200: Foo, **error_responses(404, 409)}`."""
    return {
        code: OpenApiResponse(ErrorResponseSerializer, description=_DESCRIPTIONS.get(code, ""))
        for code in status_codes
    }
