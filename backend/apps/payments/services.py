"""UPI repayments through a payment gateway.

An agent raises an order for a loan, the customer pays in the gateway's checkout, and
the payment becomes a UPI collection once the gateway vouches for it: through the
checkout's signature (Razorpay), a signed webhook, or by asking the gateway for the
order's payments (Cashfree's checkout, or a webhook that never arrived). These can report
the same payment in any order: the order row lock and the unique gateway payment id make
sure it is recorded exactly once.
"""

import json
import logging
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.audit.models import AuditAction
from apps.audit.services import log_event, snapshot
from apps.collections.services import check_can_collect, record_gateway_payment
from apps.core.exceptions import (
    DomainError,
    IdempotencyConflict,
    InvalidStateTransition,
    OverCollection,
    ResourceNotFound,
    ValidationFailed,
)
from apps.core.money import ZERO, to_money
from apps.core.numbering import gateway_order_receipt
from apps.loans.models import Loan

from . import selectors
from .exceptions import InvalidSignature, OrderAlreadyPaid, PaymentAmountMismatch
from .models import CHECKOUT_WINDOW, GatewayOrder, WebhookEvent
from .providers import (
    CheckoutCustomer,
    GatewayEvent,
    GatewayPayment,
    MockProvider,
    PaymentOutcome,
    PaymentProvider,
    get_provider,
)
from .providers.mock import MockOutcome

logger = logging.getLogger(__name__)

# How far back `sync_open_orders` asks the gateway about orders that were never paid.
SYNC_LOOKBACK = timedelta(days=1)

ORDER_AUDIT_FIELDS = ("provider", "provider_order_id", "receipt", "loan", "agent", "amount")
PAYMENT_AUDIT_FIELDS = (
    "status",
    "provider_payment_id",
    "collection",
    "paid_at",
    "failed_at",
    "failure_reason",
)


def create_order(
    actor,
    *,
    loan: Loan,
    amount: Decimal | str,
    idempotency_key: uuid.UUID,
) -> tuple[GatewayOrder, bool]:
    """Raise a UPI payment order for `loan`. Returns `(order, created)`.

    Open orders reserve their amount for the checkout window, so concurrent orders can
    never add up to more than the outstanding balance. Asking again for the same amount
    while an order is still open returns that order instead of creating another.
    """
    amount = to_money(amount)
    if amount <= ZERO:
        raise ValidationFailed("Amount must be greater than zero.")
    provider = get_provider()

    with transaction.atomic():
        loan = (
            Loan.objects.select_for_update(of=("self",))
            .select_related("customer", "branch")
            .get(pk=loan.pk)
        )

        existing = GatewayOrder.objects.filter(agent=actor, idempotency_key=idempotency_key).first()
        if existing is not None:
            if (existing.loan_id, existing.amount) != (loan.pk, amount):
                raise IdempotencyConflict(details={"receipt": existing.receipt})
            return existing, False

        check_can_collect(actor, loan)
        pending = selectors.open_orders(loan).filter(provider=provider.code)
        reusable = pending.filter(agent=actor, amount=amount).order_by("-created_at").first()
        if reusable is not None:
            return reusable, False

        reserved = selectors.reserved_amount(loan)
        if amount > loan.outstanding - reserved:
            raise OverCollection(
                "The amount exceeds the outstanding balance not already awaiting payment.",
                details={
                    "outstanding": str(loan.outstanding),
                    "awaiting_payment": str(reserved),
                    "amount": str(amount),
                },
            )

        receipt = gateway_order_receipt(loan.branch.code)
        # Called under the loan lock so two orders cannot reserve the same balance; the
        # provider's short request timeout bounds how long the lock is held.
        customer = loan.customer
        provider_order = provider.create_order(
            amount,
            receipt,
            notes={
                "receipt": receipt,
                "loan_number": loan.loan_number,
                "customer_code": customer.customer_code,
            },
            customer=CheckoutCustomer(
                customer_id=customer.customer_code,
                name=customer.full_name,
                phone=customer.phone,
                email=customer.email or "",
            ),
        )
        order = GatewayOrder.objects.create(
            provider=provider.code,
            provider_order_id=provider_order.order_id,
            checkout_token=provider_order.checkout_token,
            receipt=receipt,
            loan=loan,
            agent=actor,
            amount=amount,
            raw_payload=provider_order.raw,
            idempotency_key=idempotency_key,
        )
        log_event(
            actor,
            AuditAction.GATEWAY_ORDER_CREATED,
            order,
            after=snapshot(order, (*ORDER_AUDIT_FIELDS, "status")),
        )
    return order, True


def verify_payment(
    actor, *, provider_order_id: str, payment_id: str, signature: str
) -> tuple[GatewayOrder, bool]:
    """Turn a checkout success into a UPI collection. Returns `(order, replayed)`.

    The signature is recomputed over the order id we stored, never the one the client sent.
    The order ends PAID with its receipt, or REFUND_DUE if the loan can no longer take it.
    """
    order = GatewayOrder.objects.filter(provider_order_id=provider_order_id, agent=actor).first()
    if order is None:
        raise ResourceNotFound("Payment order not found.", details={"order_id": provider_order_id})
    provider = _provider_for(order)
    if not provider.verify_checkout(order.provider_order_id, payment_id, signature):
        raise InvalidSignature(details={"order_id": order.provider_order_id})
    return _capture(
        order,
        actor=actor,
        payment_id=payment_id,
        payload={"source": "checkout", "payment_id": payment_id},
    )


def mock_pay(actor, *, order_id: int, outcome: str) -> GatewayOrder:
    """Complete checkout on the mock gateway. Success goes through `verify_payment`."""
    provider = get_provider()
    if not isinstance(provider, MockProvider):
        raise ResourceNotFound("The mock gateway is not enabled.")
    order = GatewayOrder.objects.filter(pk=order_id, agent=actor).first()
    if order is None:
        raise ResourceNotFound("Payment order not found.", details={"order_id": order_id})

    payment_id = provider.payment_id_for(order.provider_order_id, outcome=outcome)
    if outcome == MockOutcome.SUCCESS:
        verify_payment(
            actor,
            provider_order_id=order.provider_order_id,
            payment_id=payment_id,
            signature=provider.sign_checkout(order.provider_order_id, payment_id),
        )
    else:
        _record_failure(
            order,
            actor=actor,
            reason="Payment declined by the customer's bank.",
            payload={"source": "mock", "payment_id": payment_id},
            ignore_closed=False,
        )
    return selectors.gateway_orders().get(pk=order.pk)


def refresh_order(actor, order: GatewayOrder) -> tuple[GatewayOrder, bool]:
    """Ask the gateway how `order`'s payment attempts stand and record what it reports.
    Returns `(order, payment_in_progress)`.

    This is how a Cashfree checkout is confirmed, since its checkout returns nothing the
    browser could prove, and how a payment whose webhook was lost gets picked up. A
    captured payment issues the receipt exactly as the webhook would; when the customer's
    latest attempt failed, the order is marked failed and stays payable.
    `payment_in_progress` is true while that latest attempt is still undecided and payable,
    even on an order an earlier attempt marked failed, so the agent is not told to take cash
    for a payment that may still go through.
    Safe to repeat.
    """
    if order.status in GatewayOrder.CAPTURED_STATUSES:
        return order, False
    provider = _provider_for(order)
    # The gateway is asked before any row is locked; recording the answer re-checks state.
    payments = provider.fetch_payments(order.provider_order_id)
    # Each new attempt supersedes the earlier ones, which the gateway may leave undecided
    # forever (an abandoned QR stays PENDING), so the latest attempt speaks for the order.
    latest = max(payments, key=_attempt_order, default=None)
    in_progress = latest is not None and latest.is_live(timezone.now())

    captured = next((p for p in payments if p.outcome == PaymentOutcome.CAPTURED), None)
    if captured is not None:
        _capture(
            order,
            actor=actor,
            payment_id=captured.payment_id,
            payload={"source": "status_check", "payment": captured.raw},
            amount=captured.amount,
            paid_at=captured.occurred_at,
        )
    elif (
        latest is not None
        and latest.outcome == PaymentOutcome.FAILED
        and order.status == GatewayOrder.Status.CREATED
    ):
        _record_failure(
            order,
            actor=actor,
            reason=latest.failure_reason,
            payload={"source": "status_check", "payment": latest.raw},
            ignore_closed=True,
        )
    order = selectors.gateway_orders().get(pk=order.pk)
    return order, in_progress and order.status in GatewayOrder.OPEN_STATUSES


def _attempt_order(payment: GatewayPayment) -> tuple[datetime, int, str]:
    """Attempts by when they started; gateway ids grow over time and break ties."""
    started = payment.started_at or datetime.min.replace(tzinfo=UTC)
    numeric = int(payment.payment_id) if payment.payment_id.isdigit() else 0
    return started, numeric, payment.payment_id


def sync_open_orders(*, now: datetime | None = None) -> list[GatewayOrder]:
    """Check recent unpaid orders with the gateway, picking up payments whose webhook was
    lost. Returns the orders whose status changed. Safe to run repeatedly."""
    provider = get_provider()
    since = (now or timezone.now()) - SYNC_LOOKBACK
    pending = GatewayOrder.objects.filter(
        provider=provider.code,
        status__in=(*GatewayOrder.OPEN_STATUSES, GatewayOrder.Status.EXPIRED),
        created_at__gte=since,
    ).order_by("pk")
    changed = []
    for order in pending:
        try:
            refreshed, _ = refresh_order(None, order)
        except DomainError as exc:
            logger.warning("Could not sync order %s: %s %s", order, exc.code, exc.message)
            continue
        if refreshed.status != order.status:
            changed.append(refreshed)
    return changed


def handle_webhook(
    *, raw_body: bytes, signature: str, timestamp: str = "", event_id: str = ""
) -> tuple[WebhookEvent, bool]:
    """Verify, store and apply a gateway webhook. Returns `(event, duplicate)`.

    Deliveries are deduplicated through the inbox. An event that cannot be applied keeps
    its error and stays unprocessed for follow-up; a redelivery retries it.
    """
    provider = get_provider()
    if not provider.verify_webhook(raw_body, signature, timestamp=timestamp):
        raise InvalidSignature("The webhook signature could not be verified.")
    try:
        payload = json.loads(raw_body)
    except ValueError:
        payload = None
    if not isinstance(payload, dict):
        raise ValidationFailed("The webhook body must be a JSON object.")
    event = provider.parse_webhook(payload, event_id=event_id)

    with transaction.atomic():
        inbox, _ = WebhookEvent.objects.select_for_update().get_or_create(
            provider=provider.code,
            event_id=event.event_id,
            defaults={"event_type": event.event_type, "payload": payload},
        )
        if inbox.processed_at is not None:
            return inbox, True
        _process(inbox, provider, actor=None)
    return inbox, False


def retry_webhook_event(actor, event: WebhookEvent) -> WebhookEvent:
    """Apply a stored event that failed earlier, once its cause has been fixed.

    For example, an event that reached us before the order it refers to was stored.
    A failure is stored on the event again.
    """
    with transaction.atomic():
        inbox = WebhookEvent.objects.select_for_update().get(pk=event.pk)
        if inbox.processed_at is not None:
            raise InvalidStateTransition(
                "This event has already been applied.", details={"event_id": inbox.event_id}
            )
        provider = get_provider()
        if provider.code != inbox.provider:
            raise ValidationFailed(
                "This event came from a gateway that is no longer active.",
                code="GATEWAY_MISMATCH",
                details={"event_provider": inbox.provider, "active_provider": provider.code},
            )
        _process(inbox, provider, actor=actor)
    return inbox


def expire_stale_orders(*, now: datetime | None = None) -> list[GatewayOrder]:
    """Close orders with no payment attempt once the checkout window has passed.

    Failed orders keep their status and reason. An expired order can still be paid: the
    gateway may capture a payment late, and money already received is recorded, or marked
    for refund when the balance was paid in the meantime. Safe to run repeatedly.
    """
    cutoff = (now or timezone.now()) - CHECKOUT_WINDOW
    with transaction.atomic():
        stale = list(
            GatewayOrder.objects.select_for_update(skip_locked=True, of=("self",))
            .filter(status=GatewayOrder.Status.CREATED, created_at__lt=cutoff)
            .select_related("loan")
            .order_by("pk")
        )
        for order in stale:
            before = snapshot(order, ("status",))
            order.transition_to(GatewayOrder.Status.EXPIRED)
            order.save(update_fields=["status", "updated_at"])
            log_event(
                None,
                AuditAction.GATEWAY_ORDER_EXPIRED,
                order,
                before=before,
                after=snapshot(order, ("status",)),
            )
    return stale


def _process(inbox: WebhookEvent, provider: PaymentProvider, *, actor) -> None:
    """Apply a stored event; a business-rule failure is kept on it for follow-up."""
    event = provider.parse_webhook(inbox.payload, event_id=inbox.event_id)
    try:
        with transaction.atomic():
            _apply_event(provider, event, inbox.payload, actor=actor)
    except DomainError as exc:
        inbox.error = f"{exc.code}: {exc.message}"
        logger.warning("Webhook %s was not applied: %s", inbox, inbox.error)
    else:
        inbox.processed_at = timezone.now()
        inbox.error = ""
    inbox.save(update_fields=["processed_at", "error", "updated_at"])


def _apply_event(
    provider: PaymentProvider, event: GatewayEvent, payload: dict[str, Any], *, actor
) -> None:
    if event.outcome not in (PaymentOutcome.CAPTURED, PaymentOutcome.FAILED):
        return
    order = GatewayOrder.objects.filter(
        provider=provider.code, provider_order_id=event.order_id
    ).first()
    if order is None:
        raise ResourceNotFound(
            "No payment order matches this event.", details={"order_id": event.order_id}
        )
    if not event.payment_id:
        raise ValidationFailed("The event carries no payment id.")

    if event.outcome == PaymentOutcome.CAPTURED:
        _capture(
            order,
            actor=actor,
            payment_id=event.payment_id,
            payload=payload,
            amount=event.amount,
            paid_at=event.occurred_at,
        )
    else:
        _record_failure(
            order,
            actor=actor,
            reason=event.failure_reason,
            payload=payload,
            ignore_closed=True,
        )


def _capture(
    order: GatewayOrder,
    *,
    actor,
    payment_id: str,
    payload: dict[str, Any],
    amount: Decimal | None = None,
    paid_at: datetime | None = None,
) -> tuple[GatewayOrder, bool]:
    """Record a captured payment once. Returns `(order, replayed)`.

    The gateway already holds the money, so a payment the loan can no longer absorb (it
    was paid off in the meantime) is kept on the order as REFUND_DUE rather than refused.
    """
    with transaction.atomic():
        order = (
            GatewayOrder.objects.select_for_update(of=("self",))
            .select_related("loan", "agent", "collection")
            .get(pk=order.pk)
        )
        if order.status in GatewayOrder.CAPTURED_STATUSES:
            if order.provider_payment_id != payment_id:
                raise OrderAlreadyPaid(
                    details={
                        "order_id": order.provider_order_id,
                        "paid_with": order.provider_payment_id,
                        "payment_id": payment_id,
                    }
                )
            return order, True
        if amount is not None and amount != order.amount:
            raise PaymentAmountMismatch(
                details={"order_amount": str(order.amount), "captured_amount": str(amount)}
            )

        before = snapshot(order, PAYMENT_AUDIT_FIELDS)
        paid_at = min(paid_at, timezone.now()) if paid_at else timezone.now()
        try:
            # The collection belongs to the agent who raised the order, even when the
            # webhook reports the payment.
            collection, _ = record_gateway_payment(
                agent=order.agent,
                loan=order.loan,
                amount=order.amount,
                gateway_payment_id=payment_id,
                collected_at=paid_at,
                remarks=f"UPI payment for order {order.receipt}",
            )
        except OverCollection as exc:
            order.transition_to(GatewayOrder.Status.REFUND_DUE)
            order.failure_reason = f"Refund the customer: {exc.message}"
            action = AuditAction.GATEWAY_PAYMENT_REFUND_DUE
            logger.warning("Payment %s on order %s needs a refund", payment_id, order)
        else:
            order.transition_to(GatewayOrder.Status.PAID)
            order.collection = collection
            # A retry that went through; the earlier attempt's reason no longer applies.
            order.failure_reason = ""
            paid_at = collection.collected_at
            action = AuditAction.GATEWAY_PAYMENT_CAPTURED
        order.provider_payment_id = payment_id
        order.paid_at = paid_at
        order.raw_payload = payload
        order.save(
            update_fields=[
                "status",
                "collection",
                "provider_payment_id",
                "paid_at",
                "failure_reason",
                "raw_payload",
                "updated_at",
            ]
        )
        log_event(actor, action, order, before=before, after=snapshot(order, PAYMENT_AUDIT_FIELDS))
    return order, False


def _record_failure(
    order: GatewayOrder,
    *,
    actor,
    reason: str,
    payload: dict[str, Any],
    ignore_closed: bool,
) -> GatewayOrder:
    """Mark a failed attempt. The customer may still retry, so a failed order can be paid.

    With `ignore_closed`, a failure reported after the order was paid or expired (a late
    webhook for an earlier attempt) is a no-op instead of an error.
    """
    with transaction.atomic():
        order = (
            GatewayOrder.objects.select_for_update(of=("self",))
            .select_related("loan")
            .get(pk=order.pk)
        )
        if ignore_closed and order.status not in GatewayOrder.OPEN_STATUSES:
            return order

        before = snapshot(order, PAYMENT_AUDIT_FIELDS)
        if order.status != GatewayOrder.Status.FAILED:
            order.transition_to(GatewayOrder.Status.FAILED)
        order.failed_at = timezone.now()
        order.failure_reason = reason or "The payment failed."
        order.raw_payload = payload
        order.save(
            update_fields=["status", "failed_at", "failure_reason", "raw_payload", "updated_at"]
        )
        log_event(
            actor,
            AuditAction.GATEWAY_PAYMENT_FAILED,
            order,
            before=before,
            after=snapshot(order, PAYMENT_AUDIT_FIELDS),
        )
    return order


def _provider_for(order: GatewayOrder) -> PaymentProvider:
    provider = get_provider()
    if provider.code != order.provider:
        raise ValidationFailed(
            "This order was raised through a gateway that is no longer active.",
            code="GATEWAY_MISMATCH",
            details={"order_provider": order.provider, "active_provider": provider.code},
        )
    return provider
