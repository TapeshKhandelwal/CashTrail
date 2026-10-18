"""Razorpay Orders API, Standard Checkout signatures and webhooks."""

import logging
from datetime import UTC, datetime
from decimal import Decimal
from functools import cached_property
from typing import Any

import razorpay
import requests
from razorpay.errors import BadRequestError, ServerError
from razorpay.errors import GatewayError as SdkGatewayError

from apps.core.money import money_to_paise, paise_to_money

from ..exceptions import GatewayError
from ..models import GatewayProvider
from .base import (
    CheckoutCustomer,
    GatewayEvent,
    GatewayPayment,
    PaymentOutcome,
    ProviderOrder,
    signature_matches,
)

logger = logging.getLogger(__name__)

CHECKOUT_SCRIPT = "https://checkout.razorpay.com/v1/checkout.js"

# (connect, read) seconds. Order creation runs while the loan row is locked.
REQUEST_TIMEOUT = (3, 10)

SDK_ERRORS = (BadRequestError, SdkGatewayError, ServerError, requests.RequestException)

EVENT_OUTCOMES = {
    "payment.captured": PaymentOutcome.CAPTURED,
    "order.paid": PaymentOutcome.CAPTURED,
    "payment.failed": PaymentOutcome.FAILED,
}

# A refunded payment was captured first; refunds are handled outside reconciliation.
PAYMENT_OUTCOMES = {
    "captured": PaymentOutcome.CAPTURED,
    "refunded": PaymentOutcome.CAPTURED,
    "failed": PaymentOutcome.FAILED,
}


def _timestamp(value: Any) -> datetime | None:
    return datetime.fromtimestamp(value, tz=UTC) if isinstance(value, int) else None


def _amount(value: Any) -> Decimal | None:
    return paise_to_money(value) if isinstance(value, int) else None


def _failure_reason(payment: dict[str, Any]) -> str:
    return str(payment.get("error_description") or payment.get("error_reason") or "")


class RazorpayProvider:
    code = GatewayProvider.RAZORPAY
    currency = "INR"
    checkout_script = CHECKOUT_SCRIPT

    def __init__(self, *, key_id: str, key_secret: str, webhook_secret: str):
        self.key_id = key_id
        self.key_secret = key_secret
        self.webhook_secret = webhook_secret

    @property
    def environment(self) -> str:
        return "live" if self.key_id.startswith("rzp_live_") else "test"

    @cached_property
    def client(self) -> razorpay.Client:
        return razorpay.Client(auth=(self.key_id, self.key_secret))

    def create_order(
        self,
        amount: Decimal,
        receipt: str,
        notes: dict[str, str],
        *,
        customer: CheckoutCustomer | None = None,
    ) -> ProviderOrder:
        # Standard Checkout takes the customer as prefill in the browser, not on the order.
        request = {
            "amount": money_to_paise(amount),
            "currency": self.currency,
            "receipt": receipt,
            "notes": notes,
        }
        try:
            order = self.client.order.create(request, timeout=REQUEST_TIMEOUT)
            return ProviderOrder(
                order_id=order["id"],
                amount_paise=order["amount"],
                currency=order["currency"],
                raw=order,
            )
        except (*SDK_ERRORS, KeyError, ValueError) as exc:
            logger.warning("Razorpay order creation failed for %s: %r", receipt, exc)
            raise GatewayError(details={"provider": self.code}) from exc

    def verify_checkout(self, order_id: str, payment_id: str, signature: str) -> bool:
        return signature_matches(self.key_secret, f"{order_id}|{payment_id}", signature)

    def verify_webhook(self, raw_body: bytes, signature: str, *, timestamp: str = "") -> bool:
        return signature_matches(self.webhook_secret, raw_body, signature)

    def parse_webhook(self, payload: dict[str, Any], *, event_id: str = "") -> GatewayEvent:
        event_type = str(payload.get("event") or "")
        entities = payload.get("payload") or {}
        payment = (entities.get("payment") or {}).get("entity") or {}
        order = (entities.get("order") or {}).get("entity") or {}
        payment_id = str(payment.get("id") or "")
        order_id = str(payment.get("order_id") or order.get("id") or "")
        return GatewayEvent(
            # Razorpay sends X-Razorpay-Event-Id; without it, type + entity identify a delivery.
            event_id=event_id or f"{event_type}:{payment_id or order_id}",
            event_type=event_type,
            order_id=order_id,
            payment_id=payment_id,
            amount=_amount(payment.get("amount")),
            occurred_at=_timestamp(payment.get("created_at")),
            failure_reason=_failure_reason(payment),
            outcome=EVENT_OUTCOMES.get(event_type),
        )

    def fetch_payments(self, order_id: str) -> list[GatewayPayment]:
        try:
            response = self.client.order.payments(order_id, timeout=REQUEST_TIMEOUT)
            items = response["items"]
        except (*SDK_ERRORS, KeyError, TypeError) as exc:
            logger.warning("Razorpay payment lookup failed for %s: %r", order_id, exc)
            raise GatewayError(details={"provider": self.code}) from exc
        return [
            GatewayPayment(
                payment_id=str(item.get("id") or ""),
                # created/authorized have not settled into a final state yet.
                outcome=PAYMENT_OUTCOMES.get(item.get("status"), PaymentOutcome.PENDING),
                amount=_amount(item.get("amount")),
                started_at=_timestamp(item.get("created_at")),
                failure_reason=_failure_reason(item),
                raw=item,
            )
            for item in items
            if isinstance(item, dict)
        ]
