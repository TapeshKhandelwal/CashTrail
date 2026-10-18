from apps.core.exceptions import DomainError, ScopeViolation, ValidationFailed


class SegregationOfDuties(ScopeViolation):
    code = "SEGREGATION_OF_DUTIES"
    message = "The same person cannot both handle the cash and verify it."


class PendingSubmissionExists(DomainError):
    code = "PENDING_SUBMISSION_EXISTS"
    message = "You already have a cash submission awaiting review."
    status_code = 409


class DenominationMismatch(ValidationFailed):
    code = "DENOMINATION_MISMATCH"
    message = "The counted denominations do not add up to the amount."
