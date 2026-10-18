from datetime import datetime
from decimal import Decimal
from typing import Any

from django.db.models import QuerySet, Sum
from django.db.models.fields.json import KT
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.core.money import ZERO, money_to_paise
from apps.loans.models import Loan

from .models import CHECKOUT_WINDOW, GatewayOrder, WebhookEvent
from .providers import PaymentProvider


def gateway_orders() -> QuerySet[GatewayOrder]:
    return GatewayOrder.objects.select_related(
        "loan__customer", "loan__branch", "agent", "collection"
    )


def webhook_events() -> QuerySet[WebhookEvent]:
    """Stored webhooks with the order and payment they refer to, in Razorpay's payload
    layout (which the mock gateway shares) or Cashfree's."""
    return WebhookEvent.objects.annotate(
        order_id=Coalesce(
            KT("payload__payload__payment__entity__order_id"),
            KT("payload__data__order__order_id"),
        ),
        payment_id=Coalesce(
            KT("payload__payload__payment__entity__id"),
            KT("payload__data__payment__cf_payment_id"),
        ),
    )


def open_orders(loan: Loan, *, now: datetime | None = None) -> QuerySet[GatewayOrder]:
    """Orders on `loan` a customer may still be paying; their amounts are reserved."""
    since = (now or timezone.now()) - CHECKOUT_WINDOW
    return GatewayOrder.objects.filter(
        loan=loan, status__in=GatewayOrder.OPEN_STATUSES, created_at__gte=since
    )


def reserved_amount(loan: Loan) -> Decimal:
    """What `loan`'s open orders hold back from any other repayment until they close."""
    return open_orders(loan).aggregate(total=Sum("amount"))["total"] or ZERO


def gateway_config(provider: PaymentProvider) -> dict[str, Any]:
    return {
        "provider": provider.code,
        "key_id": provider.key_id,
        "environment": provider.environment,
        "currency": provider.currency,
        "checkout_script": provider.checkout_script,
        "checkout_timeout_seconds": int(CHECKOUT_WINDOW.total_seconds()),
    }


def checkout_options(order: GatewayOrder, provider: PaymentProvider) -> dict[str, Any]:
    """Everything the client needs to open the gateway's checkout for `order`."""
    customer = order.loan.customer
    return {
        **gateway_config(provider),
        "order_id": order.provider_order_id,
        "session_id": order.checkout_token,
        "amount": order.amount,
        "amount_paise": money_to_paise(order.amount),
        "description": f"EMI repayment for loan {order.loan.loan_number}",
        "expires_at": order.expires_at,
        "prefill": {
            "name": customer.full_name,
            "contact": customer.phone,
            "email": customer.email,
        },
        "notes": {"receipt": order.receipt, "loan_number": order.loan.loan_number},
    }
