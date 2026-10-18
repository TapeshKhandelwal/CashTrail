from django.conf import settings

from .base import (
    CheckoutCustomer,
    GatewayEvent,
    GatewayPayment,
    PaymentOutcome,
    PaymentProvider,
    ProviderOrder,
)
from .cashfree import CashfreeProvider
from .mock import MockProvider
from .razorpay import RazorpayProvider

__all__ = [
    "CashfreeProvider",
    "CheckoutCustomer",
    "GatewayEvent",
    "GatewayPayment",
    "MockProvider",
    "PaymentOutcome",
    "PaymentProvider",
    "ProviderOrder",
    "RazorpayProvider",
    "get_provider",
]


def get_provider() -> PaymentProvider:
    """The gateway selected by `PAYMENT_PROVIDER`."""
    if settings.PAYMENT_PROVIDER == "razorpay":
        return RazorpayProvider(
            key_id=settings.RAZORPAY_KEY_ID,
            key_secret=settings.RAZORPAY_KEY_SECRET,
            webhook_secret=settings.RAZORPAY_WEBHOOK_SECRET,
        )
    if settings.PAYMENT_PROVIDER == "cashfree":
        return CashfreeProvider(
            app_id=settings.CASHFREE_APP_ID,
            secret_key=settings.CASHFREE_SECRET_KEY,
            environment=settings.CASHFREE_ENVIRONMENT,
            notify_url=settings.CASHFREE_NOTIFY_URL,
            return_url=settings.CASHFREE_RETURN_URL,
        )
    return MockProvider(secret=f"mock-gateway:{settings.SECRET_KEY}")
