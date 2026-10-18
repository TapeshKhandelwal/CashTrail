"""Domain errors raised by services and rendered as `{"error": {code, message, details}}`."""

from typing import Any


class DomainError(Exception):
    code = "DOMAIN_ERROR"
    message = "The request could not be completed."
    status_code = 400

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ):
        self.message = message or self.message
        self.code = code or self.code
        self.status_code = status_code or self.status_code
        self.details = details or {}
        super().__init__(self.message)

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "details": self.details}


class ValidationFailed(DomainError):
    code = "VALIDATION_FAILED"
    message = "The request breaks a business rule."
    status_code = 422


class ResourceNotFound(DomainError):
    code = "NOT_FOUND"
    message = "The requested record was not found."
    status_code = 404


class ScopeViolation(DomainError):
    code = "SCOPE_VIOLATION"
    message = "You are not allowed to act on this record."
    status_code = 403


class InvalidStateTransition(DomainError):
    code = "INVALID_STATE_TRANSITION"
    message = "This action is not allowed in the record's current state."
    status_code = 409


class RecordLocked(DomainError):
    code = "RECORD_LOCKED"
    message = "This record is reconciled and can no longer be modified."
    status_code = 409


class OverCollection(DomainError):
    code = "OVER_COLLECTION"
    message = "The amount exceeds the outstanding balance."
    status_code = 422


class PossibleDuplicate(DomainError):
    code = "POSSIBLE_DUPLICATE"
    message = "A matching entry was recorded moments ago."
    status_code = 409


class DuplicateBankReference(DomainError):
    code = "DUPLICATE_BANK_REFERENCE"
    message = "This bank reference has already been used for this account."
    status_code = 409


class IdempotencyConflict(DomainError):
    code = "IDEMPOTENCY_CONFLICT"
    message = "This Idempotency-Key was already used with a different payload."
    status_code = 422
