import hashlib
import hmac
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Protocol


class PaymentOutcome(StrEnum):
    """Where a payment attempt stands, in terms every gateway maps onto."""

    CAPTURED = "captured"
    FAILED = "failed"
    PENDING = "pending"


@dataclass(frozen=True)
class CheckoutCustomer:
    """Who pays; gateways that run their own checkout need it when the order is raised."""

    customer_id: str
    name: str
    phone: str
    email: str = ""


@dataclass(frozen=True)
class ProviderOrder:
    order_id: str
    amount_paise: int
    currency: str
    raw: dict[str, Any]
    # What the gateway's checkout opens with, when the order id alone is not enough.
    checkout_token: str = ""


@dataclass(frozen=True)
class GatewayEvent:
    """A webhook reduced to what reconciliation needs, independent of the provider's format."""

    event_id: str
    event_type: str
    order_id: str
    payment_id: str
    amount: Decimal | None
    occurred_at: datetime | None
    failure_reason: str = ""
    # Empty for events reconciliation does not act on.
    outcome: PaymentOutcome | None = None


@dataclass(frozen=True)
class GatewayPayment:
    """One payment attempt on an order, as the gateway reports it when asked."""

    payment_id: str
    outcome: PaymentOutcome
    amount: Decimal | None
    started_at: datetime | None
    # When the attempt reached its final state, or for an undecided one, when it stops being
    # payable (an expired QR); None while it can still complete.
    finished_at: datetime | None = None
    failure_reason: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def occurred_at(self) -> datetime | None:
        return self.finished_at or self.started_at

    def is_live(self, now: datetime) -> bool:
        """Undecided and still payable."""
        return self.outcome == PaymentOutcome.PENDING and (
            self.finished_at is None or self.finished_at > now
        )


class PaymentProvider(Protocol):
    code: str
    key_id: str
    currency: str
    # "test"/"live" for Razorpay, "sandbox"/"production" for Cashfree; what the checkout runs in.
    environment: str
    checkout_script: str

    def create_order(
        self,
        amount: Decimal,
        receipt: str,
        notes: dict[str, str],
        *,
        customer: CheckoutCustomer,
    ) -> ProviderOrder:
        """Register an order with the gateway; raises `GatewayError` when it cannot."""
        ...

    def verify_checkout(self, order_id: str, payment_id: str, signature: str) -> bool:
        """Check the signature the checkout returned. Gateways whose checkout returns none
        reject every signature; their payments are confirmed with `fetch_payments`."""
        ...

    def verify_webhook(self, raw_body: bytes, signature: str, *, timestamp: str = "") -> bool: ...

    def parse_webhook(self, payload: dict[str, Any], *, event_id: str = "") -> GatewayEvent: ...

    def fetch_payments(self, order_id: str) -> list[GatewayPayment]:
        """The payment attempts the gateway holds for an order; raises `GatewayError`."""
        ...


def hmac_sha256(secret: str, message: bytes | str) -> str:
    if isinstance(message, str):
        message = message.encode()
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def signature_matches(secret: str, message: bytes | str, signature: str) -> bool:
    if not secret or not signature:
        return False
    return digests_equal(hmac_sha256(secret, message), signature)


def digests_equal(expected: str, received: str) -> bool:
    """Constant-time comparison that also copes with a header carrying non-ASCII bytes,
    which `compare_digest` refuses for `str` (it would surface as a 500)."""
    return hmac.compare_digest(expected.encode(), received.encode("utf-8", "surrogateescape"))
