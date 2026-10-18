import base64
import hashlib
import hmac
import json
import re
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from urllib.parse import unquote

from django.utils import timezone

from apps.core.money import money_to_paise
from apps.payments.models import GatewayOrder
from apps.payments.providers.base import hmac_sha256

RAZORPAY_KEY_SECRET = "test_key_secret"
RAZORPAY_WEBHOOK_SECRET = "test_webhook_secret"


def webhook_body(
    event_type: str,
    order: GatewayOrder,
    payment_id: str,
    *,
    amount: Decimal | None = None,
    error: str = "",
) -> bytes:
    """A webhook in Razorpay's format, serialized the way the gateway sends it."""
    payment = {
        "id": payment_id,
        "entity": "payment",
        "amount": money_to_paise(amount if amount is not None else order.amount),
        "currency": "INR",
        "status": "failed" if event_type == "payment.failed" else "captured",
        "order_id": order.provider_order_id,
        "method": "upi",
        "vpa": "success@razorpay",
        "error_description": error or None,
        "created_at": int(timezone.now().timestamp()) - 5,
    }
    payload = {
        "entity": "event",
        "account_id": "acc_Test00000001",
        "event": event_type,
        "contains": ["payment"],
        "payload": {"payment": {"entity": payment}},
        "created_at": int(timezone.now().timestamp()),
    }
    return json.dumps(payload, separators=(",", ":")).encode()


def sign(secret: str, raw_body: bytes) -> str:
    return hmac_sha256(secret, raw_body)


# ------------------------------------------------------------------------------- Cashfree

CASHFREE_APP_ID = "TEST10000000cashtrail"
CASHFREE_SECRET_KEY = "cfsk_ma_test_cashtrail"
CASHFREE_SESSION_PREFIX = "session_test_"


def cashfree_payment(
    order: GatewayOrder,
    payment_id: str = "5114910000001",
    *,
    status: str = "SUCCESS",
    amount: Decimal | None = None,
    surcharge: Decimal | None = None,
    at: str = "2026-10-18T10:15:06+05:30",
    error: str = "",
) -> dict[str, Any]:
    """A payment as Cashfree's Get Payments for an Order returns it (API 2026-01-01)."""
    paid = amount if amount is not None else order.amount
    if surcharge:
        paid += surcharge
    finished = status in ("SUCCESS", "FAILED", "USER_DROPPED")
    return {
        "cf_payment_id": payment_id,
        "order_id": order.provider_order_id,
        "entity": "payment",
        "payment_amount": float(paid),
        "payment_currency": "INR",
        "order_amount": float(order.amount),
        "order_currency": "INR",
        "payment_status": status,
        "payment_message": "Simulated response message" if finished else None,
        "payment_time": at,
        "payment_completion_time": at if finished else None,
        "bank_reference": "1234567890" if status == "SUCCESS" else None,
        "is_captured": status == "SUCCESS",
        "payment_group": "upi",
        "payment_method": {"upi": {"channel": "collect", "upi_id": "testsuccess@gocash"}},
        "payment_surcharge": {
            "payment_surcharge_service_charge": float(surcharge or 0),
            "payment_surcharge_service_tax": 0,
        },
        "error_details": (
            {"error_code": "TRANSACTION_DECLINED", "error_description": error} if error else None
        ),
    }


def cashfree_webhook_body(
    event_type: str,
    order: GatewayOrder,
    payment_id: str = "5114910000001",
    *,
    amount: Decimal | None = None,
    error: str = "",
) -> bytes:
    """A payment webhook as Cashfree sends it (2026-01-01), serialized compactly."""
    status = {
        "PAYMENT_SUCCESS_WEBHOOK": "SUCCESS",
        "PAYMENT_FAILED_WEBHOOK": "FAILED",
        "PAYMENT_USER_DROPPED_WEBHOOK": "USER_DROPPED",
    }.get(event_type, "PENDING")
    payment = cashfree_payment(order, payment_id, status=status, amount=amount)
    for key in ("order_id", "entity", "order_amount", "order_currency", "error_details"):
        payment.pop(key)
    payload = {
        "data": {
            "order": {
                "order_id": order.provider_order_id,
                "order_amount": float(order.amount),
                "order_currency": "INR",
                "order_tags": None,
            },
            "payment": payment,
            "customer_details": {"customer_id": "CUS-T000001", "customer_phone": "9700000001"},
            "error_details": (
                {"error_code": "TRANSACTION_DECLINED", "error_description": error}
                if error
                else None
            ),
        },
        "event_time": "2026-10-18T10:15:09+05:30",
        "type": event_type,
    }
    return json.dumps(payload, separators=(",", ":")).encode()


def cashfree_sign(raw_body: bytes, timestamp: str, secret: str = CASHFREE_SECRET_KEY) -> str:
    digest = hmac.new(secret.encode(), timestamp.encode() + raw_body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


class FakeResponse:
    def __init__(self, status_code: int, body: Any):
        self.status_code = status_code
        self.ok = 200 <= status_code < 300
        self.text = body if isinstance(body, str) else json.dumps(body)

    def json(self, **kwargs):
        return json.loads(self.text, **kwargs)


class FakeCashfree:
    """Cashfree's PG API as the provider's HTTP session sees it: answers like the sandbox
    and records every request."""

    def __init__(self):
        self.headers: dict[str, str] = {}
        self.requests: list[SimpleNamespace] = []
        self.payments: dict[str, list[dict[str, Any]]] = {}
        self.error: Exception | FakeResponse | None = None

    def request(self, method, url, *, json=None, headers=None, timeout=None):
        self.requests.append(
            SimpleNamespace(method=method, url=url, json=json, headers=headers, timeout=timeout)
        )
        if isinstance(self.error, Exception):
            raise self.error
        if self.error is not None:
            return self.error
        path = url.split("/pg", 1)[1]
        if method == "POST" and path == "/orders":
            return FakeResponse(200, self._order(json))
        match = re.fullmatch(r"/orders/([^/]+)/payments", path)
        if method == "GET" and match:
            return FakeResponse(200, self.payments.get(unquote(match[1]), []))
        return FakeResponse(404, {"code": "order_not_found", "type": "invalid_request_error"})

    def pay(self, order: GatewayOrder, *payments: dict[str, Any]) -> None:
        self.payments[order.provider_order_id] = list(payments)

    @staticmethod
    def _order(request: dict[str, Any]) -> dict[str, Any]:
        return {
            "cf_order_id": "2149460581",
            "entity": "order",
            "order_id": request["order_id"],
            "order_amount": request["order_amount"],
            "order_currency": request["order_currency"],
            "order_status": "ACTIVE",
            "order_expiry_time": request["order_expiry_time"],
            "customer_details": request["customer_details"],
            "order_meta": request["order_meta"],
            "order_tags": request["order_tags"],
            "payment_session_id": f"{CASHFREE_SESSION_PREFIX}{request['order_id']}",
        }
