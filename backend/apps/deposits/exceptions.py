from apps.core.exceptions import DomainError


class SubmissionAlreadyDeposited(DomainError):
    code = "SUBMISSION_ALREADY_DEPOSITED"
    message = "One or more submissions are already part of a bank deposit."
    status_code = 409
