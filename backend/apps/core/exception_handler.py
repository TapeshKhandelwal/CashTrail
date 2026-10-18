"""Renders every API error as `{"error": {"code", "message", "details"}}`."""

import logging

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import SuspiciousOperation
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import DatabaseError, DataError, IntegrityError
from django.db.models import ProtectedError, RestrictedError
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import set_rollback

from .exceptions import (
    DomainError,
    DuplicateBankReference,
    OverCollection,
    RecordLocked,
    ValidationFailed,
)

logger = logging.getLogger(__name__)

LOCKED_PREFIX = "RECORD_LOCKED:"

UNIQUE_VIOLATION = "23505"
CHECK_VIOLATION = "23514"
FOREIGN_KEY_VIOLATION = "23503"
NOT_NULL_VIOLATION = "23502"
NUMERIC_OUT_OF_RANGE = "22003"
STRING_TOO_LONG = "22001"

_DUPLICATE_REQUEST = DomainError(
    "An identical request is already being processed; retry to receive its result.",
    code="DUPLICATE_REQUEST",
    status_code=409,
)

CONSTRAINT_ERRORS: dict[str, DomainError] = {
    "uniq_bank_deposit_account_reference": DuplicateBankReference(),
    "uniq_submission_pending_per_agent": DomainError(
        "You already have a cash submission awaiting review.",
        code="PENDING_SUBMISSION_EXISTS",
        status_code=409,
    ),
    "uniq_collection_agent_idempotency_key": _DUPLICATE_REQUEST,
    "uniq_submission_agent_idempotency_key": _DUPLICATE_REQUEST,
    "uniq_bank_deposit_creator_idempotency_key": _DUPLICATE_REQUEST,
    "uniq_gateway_order_agent_idempotency_key": _DUPLICATE_REQUEST,
    "uniq_collection_gateway_payment_id": DomainError(
        "This gateway payment has already been recorded.",
        code="DUPLICATE_PAYMENT",
        status_code=409,
    ),
    "uniq_active_gateway_bank_account": DomainError(
        "Only one active gateway settlement account is allowed.",
        code="GATEWAY_ACCOUNT_EXISTS",
        status_code=409,
    ),
    "loan_amount_paid_within_total": OverCollection(),
    "installment_amount_paid_within_due": OverCollection(),
    "user_branch_required_for_branch_roles": ValidationFailed(
        "Agents and branch managers must belong to a branch."
    ),
}


def _error_response(error: DomainError, headers: dict | None = None) -> Response:
    set_rollback()
    return Response({"error": error.as_dict()}, status=error.status_code, headers=headers)


def _from_api_exception(exc: exceptions.APIException) -> DomainError:
    if isinstance(exc, exceptions.ValidationError):
        details = exc.detail if isinstance(exc.detail, dict) else {"non_field_errors": exc.detail}
        return DomainError(
            "Invalid input.", code="VALIDATION_ERROR", status_code=exc.status_code, details=details
        )

    detail = exc.detail
    if isinstance(detail, dict):
        message = str(detail.get("detail", exc.default_detail))
        code = str(detail.get("code", exc.default_code))
        details = {key: value for key, value in detail.items() if key not in ("detail", "code")}
    else:
        message, code, details = str(detail), getattr(detail, "code", None) or exc.default_code, {}
        if isinstance(exc, exceptions.Throttled) and exc.wait is not None:
            details = {"retry_after_seconds": int(exc.wait)}
    return DomainError(message, code=code.upper(), status_code=exc.status_code, details=details)


def _sqlstate(exc: DatabaseError) -> str | None:
    return getattr(exc.__cause__, "sqlstate", None)


def _from_integrity_error(exc: IntegrityError) -> DomainError:
    cause = exc.__cause__
    sqlstate = _sqlstate(exc)
    constraint = getattr(getattr(cause, "diag", None), "constraint_name", None)
    if constraint in CONSTRAINT_ERRORS:
        return CONSTRAINT_ERRORS[constraint]

    details = {"constraint": constraint} if constraint else {}
    if sqlstate == UNIQUE_VIOLATION:
        return DomainError(
            "A record with these values already exists.",
            code="DUPLICATE_RECORD",
            status_code=409,
            details=details,
        )
    if sqlstate in (CHECK_VIOLATION, NOT_NULL_VIOLATION):
        return ValidationFailed("The data violates a database rule.", details=details)
    if sqlstate == FOREIGN_KEY_VIOLATION:
        return DomainError(
            "A referenced record does not exist or is still in use.",
            code="INVALID_REFERENCE",
            status_code=409,
            details=details,
        )
    return DomainError(
        "The change conflicts with existing data.", code="INTEGRITY_ERROR", status_code=409
    )


def _locked_message(exc: DatabaseError) -> str | None:
    """Integrity triggers raise `RECORD_LOCKED: <reason>`; return the reason if this is one."""
    cause = exc.__cause__
    text = getattr(getattr(cause, "diag", None), "message_primary", None) or str(exc)
    if text.startswith(LOCKED_PREFIX):
        return text.removeprefix(LOCKED_PREFIX).strip()
    return None


def exception_handler(exc, context):
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, DjangoPermissionDenied):
        exc = exceptions.PermissionDenied()
    elif isinstance(exc, DjangoValidationError):
        exc = exceptions.ValidationError(
            exc.message_dict if hasattr(exc, "error_dict") else {"non_field_errors": exc.messages}
        )

    if isinstance(exc, DomainError):
        return _error_response(exc)

    if isinstance(exc, exceptions.APIException):
        headers = {}
        if getattr(exc, "auth_header", None):
            headers["WWW-Authenticate"] = exc.auth_header
        if getattr(exc, "wait", None):
            headers["Retry-After"] = str(int(exc.wait))
        return _error_response(_from_api_exception(exc), headers)

    if isinstance(exc, ProtectedError | RestrictedError):
        return _error_response(
            DomainError(
                "This record is referenced by other records and cannot be deleted.",
                code="PROTECTED_RECORD",
                status_code=409,
            )
        )

    if isinstance(exc, IntegrityError):
        return _error_response(_from_integrity_error(exc))

    if isinstance(exc, DataError) and _sqlstate(exc) in (NUMERIC_OUT_OF_RANGE, STRING_TOO_LONG):
        return _error_response(ValidationFailed("A value is too large to be stored."))

    if isinstance(exc, SuspiciousOperation):
        logger.warning("Suspicious request rejected: %s", exc)
        return _error_response(
            DomainError("The request could not be processed.", code="BAD_REQUEST")
        )

    if isinstance(exc, DatabaseError) and (reason := _locked_message(exc)) is not None:
        logger.warning("Blocked modification of a locked record: %s", reason)
        return _error_response(RecordLocked(reason))

    logger.exception("Unhandled error", exc_info=exc)
    return _error_response(
        DomainError(
            "Something went wrong on our side. Please try again.",
            code="INTERNAL_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    )
