"""Cashfree Payment Gateway: Orders API, the JS checkout and payment webhooks.

Cashfree's checkout returns no signature to the browser, so a payment is never taken on
the client's word: it is confirmed by asking Cashfree for the order's payments, or by a
webhook signed with the secret key.
"""

import base64
import hashlib
import hmac
import logging
import re
import secrets
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from functools import cached_property
from typing import Any
from urllib.parse import quote

import requests
from django.utils import timezone

from apps.core.money import money_to_paise, to_money

from ..exceptions import GatewayError
from ..models import CHECKOUT_WINDOW, GatewayProvider
from .base import (
    CheckoutCustomer,
    GatewayEvent,
    GatewayPayment,
    PaymentOutcome,
    ProviderOrder,
    digests_equal,
)

logger = logging.getLogger(__name__)

API_VERSION = "2026-01-01"
BASE_URLS = {
    "sandbox": "https://sandbox.cashfree.com/pg",
    "production": "https://api.cashfree.com/pg",
}
CHECKOUT_SCRIPT = "https://sdk.cashfree.com/js/v3/cashfree.js"

# (connect, read) seconds. Order creation runs while the loan row is locked.
REQUEST_TIMEOUT = (3, 10)

# Cashfree refuses an order that expires less than 15 minutes out. A payment captured after
# our own checkout window is still recorded (or marked for refund), so the extra minute is safe.
MIN_ORDER_EXPIRY = timedelta(minutes=16)

EVENT_OUTCOMES = {
    "PAYMENT_SUCCESS_WEBHOOK": PaymentOutcome.CAPTURED,
    "PAYMENT_FAILED_WEBHOOK": PaymentOutcome.FAILED,
    "PAYMENT_USER_DROPPED_WEBHOOK": PaymentOutcome.FAILED,
}

# PENDING and NOT_ATTEMPTED attempts are still in flight.
PAYMENT_OUTCOMES = {
    "SUCCESS": PaymentOutcome.CAPTURED,
    "FAILED": PaymentOutcome.FAILED,
    "USER_DROPPED": PaymentOutcome.FAILED,
    "CANCELLED": PaymentOutcome.FAILED,
    "VOID": PaymentOutcome.FAILED,
}

USER_DROPPED_REASON = "The customer left the payment page without paying."

_NOT_ID_CHARS = re.compile(r"[^A-Za-z0-9_-]")


def _money(value: Any) -> Decimal | None:
    """Cashfree sends rupees as JSON numbers; read them without going through binary floats."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        return to_money(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _paid_amount(payment: dict[str, Any]) -> Decimal | None:
    """What the payment put towards the order: a surcharge the customer paid on top is the
    gateway's, not a repayment."""
    amount = _money(payment.get("payment_amount"))
    surcharge = _as_dict(payment.get("payment_surcharge"))
    if amount is None:
        return None
    for key in ("payment_surcharge_service_charge", "payment_surcharge_service_tax"):
        amount -= _money(surcharge.get(key)) or Decimal(0)
    return amount


def _time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _phone(value: str) -> str:
    """Cashfree takes a 10-digit Indian mobile number."""
    return re.sub(r"\D", "", value)[-10:]


def _failure_reason(payment: dict[str, Any], error: dict[str, Any] | None) -> str:
    if payment.get("payment_status") == "USER_DROPPED":
        return USER_DROPPED_REASON
    error = error or {}
    return str(error.get("error_description") or payment.get("payment_message") or "")


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


class CashfreeProvider:
    code = GatewayProvider.CASHFREE
    currency = "INR"
    checkout_script = CHECKOUT_SCRIPT
    # The checkout opens with the order's payment session, not a public key.
    key_id = ""

    def __init__(
        self,
        *,
        app_id: str,
        secret_key: str,
        environment: str = "sandbox",
        notify_url: str = "",
        return_url: str = "",
    ):
        if environment not in BASE_URLS:
            raise ValueError(f"Unknown Cashfree environment {environment!r}.")
        self.app_id = app_id
        self.secret_key = secret_key
        self.environment = environment
        self.base_url = BASE_URLS[environment]
        self.notify_url = notify_url
        self.return_url = return_url

    @cached_property
    def session(self) -> requests.Session:
        session = requests.Session()
        session.headers.update(
            {
                "x-client-id": self.app_id,
                "x-client-secret": self.secret_key,
                "x-api-version": API_VERSION,
                "Accept": "application/json",
            }
        )
        return session

    def create_order(
        self,
        amount: Decimal,
        receipt: str,
        notes: dict[str, str],
        *,
        customer: CheckoutCustomer,
    ) -> ProviderOrder:
        amount = to_money(amount)
        # Order ids are unique across the whole Cashfree account, which every deployment on
        # the same keys shares, while our receipt sequence is only unique per database.
        order_id = f"{receipt}-{secrets.token_hex(3)}"
        expires_at = timezone.now() + max(CHECKOUT_WINDOW, MIN_ORDER_EXPIRY)
        order_meta = {
            # The receipt is recorded as a UPI collection, so the checkout offers only UPI.
            "payment_methods": "upi",
            **({"notify_url": self.notify_url} if self.notify_url else {}),
            **({"return_url": self._return_url(order_id)} if self.return_url else {}),
        }
        details = {
            "customer_id": _NOT_ID_CHARS.sub("_", customer.customer_id),
            "customer_phone": _phone(customer.phone),
            **({"customer_name": customer.name} if len(customer.name) >= 3 else {}),
            **({"customer_email": customer.email} if customer.email else {}),
        }
        body = {
            "order_id": order_id,
            # Two-decimal amounts within NUMERIC(14,2) survive the float round trip exactly.
            "order_amount": float(amount),
            "order_currency": self.currency,
            "order_expiry_time": expires_at.isoformat(timespec="seconds"),
            "customer_details": details,
            "order_meta": order_meta,
            # Carries our receipt, so the order is easy to find from the dashboard.
            "order_tags": {key: value for key, value in notes.items() if value},
        }
        order = self._request("POST", "/orders", json=body, request_id=receipt)
        try:
            order_amount = _money(order["order_amount"])
            if order_amount != amount or not order["payment_session_id"]:
                raise ValueError("Cashfree returned an order that does not match the request.")
            return ProviderOrder(
                order_id=str(order["order_id"]),
                amount_paise=money_to_paise(order_amount),
                currency=str(order["order_currency"]),
                raw=_jsonable(order),
                checkout_token=str(order["payment_session_id"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("Cashfree returned an unusable order for %s: %r", receipt, exc)
            raise GatewayError(details={"provider": self.code}) from exc

    def verify_checkout(self, order_id: str, payment_id: str, signature: str) -> bool:
        return False

    def verify_webhook(self, raw_body: bytes, signature: str, *, timestamp: str = "") -> bool:
        """`x-webhook-signature` is base64(HMAC-SHA256(timestamp + raw body, secret key))."""
        if not (self.secret_key and signature and timestamp):
            return False
        digest = hmac.new(
            self.secret_key.encode(),
            timestamp.encode("utf-8", "surrogateescape") + raw_body,
            hashlib.sha256,
        ).digest()
        return digests_equal(base64.b64encode(digest).decode(), signature)

    def parse_webhook(self, payload: dict[str, Any], *, event_id: str = "") -> GatewayEvent:
        event_type = str(payload.get("type") or "")
        data = _as_dict(payload.get("data"))
        order = _as_dict(data.get("order"))
        payment = _as_dict(data.get("payment"))
        payment_id = str(payment.get("cf_payment_id") or "")
        order_id = str(order.get("order_id") or "")
        return GatewayEvent(
            # A payment reaches each terminal state once, whichever endpoint it was sent to.
            event_id=event_id or f"{event_type}:{payment_id or order_id}",
            event_type=event_type,
            order_id=order_id,
            payment_id=payment_id,
            amount=_paid_amount(payment),
            occurred_at=_time(payment.get("payment_completion_time"))
            or _time(payment.get("payment_time")),
            failure_reason=_failure_reason(payment, _as_dict(data.get("error_details"))),
            outcome=EVENT_OUTCOMES.get(event_type),
        )

    def fetch_payments(self, order_id: str) -> list[GatewayPayment]:
        items = self._request("GET", f"/orders/{quote(order_id, safe='')}/payments")
        if not isinstance(items, list):
            logger.warning("Cashfree returned an unusable payment list for %s", order_id)
            raise GatewayError(details={"provider": self.code})
        return [
            GatewayPayment(
                payment_id=str(item.get("cf_payment_id") or ""),
                outcome=PAYMENT_OUTCOMES.get(item.get("payment_status"), PaymentOutcome.PENDING),
                amount=_paid_amount(item),
                started_at=_time(item.get("payment_time")),
                # Cashfree leaves an abandoned QR attempt PENDING but sets this once it expires.
                finished_at=_time(item.get("payment_completion_time")),
                failure_reason=_failure_reason(item, _as_dict(item.get("error_details"))),
                raw=_jsonable(item),
            )
            for item in items
            if isinstance(item, dict)
        ]

    def _return_url(self, order_id: str) -> str:
        return self.return_url.replace("{order_id}", quote(order_id, safe=""))

    def _request(self, method: str, path: str, *, json: Any = None, request_id: str = "") -> Any:
        headers = {"x-request-id": request_id} if request_id else {}
        try:
            response = self.session.request(
                method,
                f"{self.base_url}{path}",
                json=json,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            logger.warning("Cashfree %s %s failed: %r", method, path, exc)
            raise GatewayError(details={"provider": self.code}) from exc
        try:
            body = response.json(parse_float=Decimal)
        except ValueError:
            body = None
        if not response.ok:
            error = _as_dict(body)
            logger.warning(
                "Cashfree %s %s returned %s: %s %s",
                method,
                path,
                response.status_code,
                error.get("code", ""),
                error.get("message", ""),
            )
            raise GatewayError(
                details={"provider": self.code, "gateway_code": str(error.get("code", ""))}
            )
        return body


def _jsonable(value: Any) -> Any:
    """Decimals parsed from the response, as strings, so the payload can be stored as JSON."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value
