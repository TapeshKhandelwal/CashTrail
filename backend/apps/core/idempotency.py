"""`Idempotency-Key` handling for create endpoints that move money.

Views read the key with `require_idempotency_key(request)` and pass it to the
service, which stores it under a unique constraint and returns the original
record on a replay. Replays are answered with `200` and `Idempotent-Replayed: true`.
"""

import uuid

from django.db import connection
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter
from rest_framework.response import Response

from .exceptions import DomainError

IDEMPOTENCY_HEADER = "Idempotency-Key"
REPLAYED_HEADER = "Idempotent-Replayed"

IDEMPOTENCY_KEY_PARAMETER = OpenApiParameter(
    name=IDEMPOTENCY_HEADER,
    type=OpenApiTypes.UUID,
    location=OpenApiParameter.HEADER,
    required=True,
    description="Client-generated UUID; retries with the same key return the original result.",
)


class IdempotencyKeyRequired(DomainError):
    code = "IDEMPOTENCY_KEY_REQUIRED"
    message = f"The {IDEMPOTENCY_HEADER} header must be a UUID."
    status_code = 400


def require_idempotency_key(request) -> uuid.UUID:
    raw = request.headers.get(IDEMPOTENCY_HEADER, "").strip()
    try:
        return uuid.UUID(raw)
    except ValueError:
        raise IdempotencyKeyRequired(details={"header": IDEMPOTENCY_HEADER}) from None


def lock_idempotency_key(scope: str, owner_id: int, key: uuid.UUID) -> None:
    """Hold requests sharing `key` until the current transaction ends.

    Call before looking the key up: a retry racing the original then waits for it to
    commit and replays its result, instead of failing on the rows the original changed.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", [f"{scope}:{owner_id}:{key}"]
        )


def created_or_replayed(data, *, created: bool) -> Response:
    if created:
        return Response(data, status=201)
    return Response(data, status=200, headers={REPLAYED_HEADER: "true"})
