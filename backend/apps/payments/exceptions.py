from apps.core.exceptions import DomainError, ValidationFailed


class GatewayError(DomainError):
    code = "GATEWAY_ERROR"
    message = "The payment gateway could not be reached. Please try again."
    status_code = 502


class InvalidSignature(DomainError):
    code = "INVALID_SIGNATURE"
    message = "The payment signature could not be verified."
    status_code = 400


class OrderAlreadyPaid(DomainError):
    code = "ORDER_ALREADY_PAID"
    message = "This order has already been paid by another payment."
    status_code = 409


class PaymentAmountMismatch(ValidationFailed):
    code = "PAYMENT_AMOUNT_MISMATCH"
    message = "The captured amount does not match the order amount."
