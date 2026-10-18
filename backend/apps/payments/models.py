from datetime import datetime, timedelta

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.models import StateMachineMixin, TimeStampedModel, money_field

# How long a customer has to complete checkout; open orders reserve their amount until then.
CHECKOUT_WINDOW = timedelta(minutes=15)


class GatewayProvider(models.TextChoices):
    RAZORPAY = "RAZORPAY", "Razorpay"
    CASHFREE = "CASHFREE", "Cashfree"
    MOCK = "MOCK", "Mock gateway"


class GatewayOrder(StateMachineMixin, TimeStampedModel):
    """A UPI payment request raised by an agent for a loan."""

    class Status(models.TextChoices):
        CREATED = "CREATED", "Awaiting payment"
        PAID = "PAID", "Paid"
        FAILED = "FAILED", "Failed"
        EXPIRED = "EXPIRED", "Expired"
        # Captured after the loan's balance was paid by other means; owed back to the customer.
        REFUND_DUE = "REFUND_DUE", "Refund due"

    OPEN_STATUSES = (Status.CREATED, Status.FAILED)
    CAPTURED_STATUSES = (Status.PAID, Status.REFUND_DUE)
    TRANSITIONS = {
        Status.CREATED: frozenset({Status.PAID, Status.REFUND_DUE, Status.FAILED, Status.EXPIRED}),
        # The customer may retry on the same order after a failed attempt.
        Status.FAILED: frozenset({Status.PAID, Status.REFUND_DUE, Status.EXPIRED}),
        # A payment captured after the checkout window closed is still money received.
        Status.EXPIRED: frozenset({Status.PAID, Status.REFUND_DUE}),
    }

    provider = models.CharField(max_length=10, choices=GatewayProvider.choices)
    provider_order_id = models.CharField(max_length=64, unique=True)
    checkout_token = models.TextField(
        blank=True,
        help_text="Session the gateway's checkout opens with (Cashfree); empty when it "
        "needs only the order id.",
    )
    receipt = models.CharField(
        max_length=40, unique=True, help_text="Our reference sent to the gateway."
    )
    loan = models.ForeignKey("loans.Loan", on_delete=models.PROTECT, related_name="gateway_orders")
    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="gateway_orders",
        db_index=False,
    )
    amount = money_field()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.CREATED)
    provider_payment_id = models.CharField(max_length=64, blank=True)
    collection = models.OneToOneField(
        "collections.Collection",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="gateway_order",
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.TextField(blank=True)
    raw_payload = models.JSONField(default=dict, blank=True)
    idempotency_key = models.UUIDField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["agent", "idempotency_key"], name="uniq_gateway_order_agent_idempotency_key"
            ),
            models.CheckConstraint(condition=Q(amount__gt=0), name="gateway_order_amount_positive"),
            models.CheckConstraint(
                condition=~Q(status="PAID") | Q(collection__isnull=False, paid_at__isnull=False),
                name="gateway_order_paid_has_collection",
            ),
            models.CheckConstraint(
                condition=~Q(status="REFUND_DUE")
                | (Q(collection__isnull=True, paid_at__isnull=False) & ~Q(provider_payment_id="")),
                name="gateway_order_refund_due_has_payment",
            ),
        ]
        indexes = [
            models.Index(fields=["agent", "status"], name="gateway_order_agent_idx"),
            models.Index(fields=["status", "created_at"], name="gateway_order_status_idx"),
        ]

    def __str__(self):
        return self.provider_order_id

    @property
    def branch_id(self) -> int:
        """Orders belong to the loan's branch, which scopes their audit entries."""
        return self.loan.branch_id

    @property
    def expires_at(self) -> datetime:
        return self.created_at + CHECKOUT_WINDOW


class WebhookEvent(TimeStampedModel):
    """Inbox of verified gateway webhooks; the unique key makes redelivery a no-op."""

    provider = models.CharField(max_length=10, choices=GatewayProvider.choices)
    event_id = models.CharField(max_length=128)
    event_type = models.CharField(max_length=64)
    payload = models.JSONField()
    processed_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["provider", "event_id"], name="uniq_webhook_event"),
        ]
        indexes = [
            models.Index(
                fields=["created_at"],
                condition=Q(processed_at__isnull=True),
                name="webhook_unprocessed_idx",
            ),
        ]

    def __str__(self):
        return f"{self.provider}:{self.event_type}:{self.event_id}"
