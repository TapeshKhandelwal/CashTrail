"""An offline gateway that speaks Razorpay's wire format.

Order and payment ids, checkout signatures and webhook payloads look exactly like
Razorpay's but are signed with a local secret, so verification and reconciliation
run through the same code as production without keys or network access.
"""

import hashlib
from decimal import Decimal

from django.db import models

from apps.core.money import money_to_paise

from ..models import GatewayProvider
from .base import CheckoutCustomer, GatewayPayment, ProviderOrder, hmac_sha256
from .razorpay import RazorpayProvider


class MockOutcome(models.TextChoices):
    SUCCESS = "success", "Payment succeeds"
    FAILURE = "failure", "Payment fails"


def _short_id(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:14]


class MockProvider(RazorpayProvider):
    code = GatewayProvider.MOCK
    environment = "test"
    checkout_script = ""

    def __init__(self, *, secret: str):
        super().__init__(key_id="", key_secret=secret, webhook_secret=secret)

    def create_order(
        self,
        amount: Decimal,
        receipt: str,
        notes: dict[str, str],
        *,
        customer: CheckoutCustomer | None = None,
    ) -> ProviderOrder:
        order_id = f"order_{_short_id(receipt)}"
        amount_paise = money_to_paise(amount)
        raw = {
            "id": order_id,
            "entity": "order",
            "amount": amount_paise,
            "currency": self.currency,
            "receipt": receipt,
            "status": "created",
            "notes": notes,
        }
        return ProviderOrder(
            order_id=order_id, amount_paise=amount_paise, currency=self.currency, raw=raw
        )

    def payment_id_for(self, order_id: str, *, outcome: str) -> str:
        """Stable per order and outcome, so paying the same order twice replays the receipt."""
        return f"pay_{_short_id(order_id, outcome)}"

    def sign_checkout(self, order_id: str, payment_id: str) -> str:
        return hmac_sha256(self.key_secret, f"{order_id}|{payment_id}")

    def sign_webhook(self, raw_body: bytes) -> str:
        return hmac_sha256(self.webhook_secret, raw_body)

    def fetch_payments(self, order_id: str) -> list[GatewayPayment]:
        """Nothing to look up: mock payments are reported the moment they happen."""
        return []
