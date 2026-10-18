"""Customer reads with their repayment position, computed in SQL.

Each figure is a correlated subquery rather than a join + GROUP BY, so annotating a
page of customers costs one query and never multiplies rows across loans.
"""

from datetime import date

from django.db.models import (
    Case,
    Count,
    DecimalField,
    F,
    IntegerField,
    OuterRef,
    Prefetch,
    QuerySet,
    Subquery,
    Sum,
    Value,
    When,
)
from django.db.models.functions import Coalesce

from apps.core.dates import business_date
from apps.core.money import ZERO
from apps.loans.models import Installment, Loan

from .models import Customer

MONEY = DecimalField(max_digits=14, decimal_places=2)
INSTALLMENT_BALANCE = F("amount_due") - F("amount_paid")
LOAN_BALANCE = F("total_payable") - F("amount_paid")


def _sum(queryset: QuerySet, group_by: str, expression) -> Coalesce:
    totals = (
        queryset.order_by()
        .values(group_by)
        .annotate(total=Sum(expression, output_field=MONEY))
        .values("total")
    )
    return Coalesce(Subquery(totals, output_field=MONEY), Value(ZERO), output_field=MONEY)


def _count(queryset: QuerySet, group_by: str) -> Coalesce:
    counts = queryset.order_by().values(group_by).annotate(total=Count("pk")).values("total")
    return Coalesce(Subquery(counts, output_field=IntegerField()), Value(0))


def _unpaid_installments(**loan_lookup) -> QuerySet[Installment]:
    return Installment.objects.filter(**loan_lookup).exclude(status=Installment.Status.PAID)


def with_dues(queryset: QuerySet[Customer], *, today: date | None = None) -> QuerySet[Customer]:
    """Annotate `outstanding`, `overdue_amount`, `due_today`, `next_due_date`, `active_loans`.

    Only active loans count: a closed loan has nothing left to collect.
    """
    today = today or business_date()
    unpaid = _unpaid_installments(loan__customer=OuterRef("pk"), loan__status=Loan.Status.ACTIVE)
    active_loans = Loan.objects.filter(customer=OuterRef("pk"), status=Loan.Status.ACTIVE)
    return queryset.annotate(
        outstanding=_sum(active_loans, "customer", LOAN_BALANCE),
        overdue_amount=_sum(
            unpaid.filter(due_date__lt=today), "loan__customer", INSTALLMENT_BALANCE
        ),
        due_today=_sum(unpaid.filter(due_date=today), "loan__customer", INSTALLMENT_BALANCE),
        next_due_date=Subquery(unpaid.order_by("due_date").values("due_date")[:1]),
        active_loans=_count(active_loans, "customer"),
    )


def loan_summaries(*, today: date | None = None) -> QuerySet[Loan]:
    """Loans with `overdue_amount` and `next_due_date`, newest disbursal first."""
    today = today or business_date()
    unpaid = _unpaid_installments(loan=OuterRef("pk"))
    return Loan.objects.annotate(
        overdue_amount=_sum(unpaid.filter(due_date__lt=today), "loan", INSTALLMENT_BALANCE),
        next_due_date=Subquery(unpaid.order_by("due_date").values("due_date")[:1]),
    ).order_by("-disbursed_on", "-pk")


def customer_list(queryset: QuerySet[Customer]) -> QuerySet[Customer]:
    return with_dues(queryset.select_related("branch", "assigned_agent"))


def customer_detail(queryset: QuerySet[Customer]) -> QuerySet[Customer]:
    return customer_list(queryset).prefetch_related(Prefetch("loans", queryset=loan_summaries()))


def agent_route(agent) -> QuerySet[Customer]:
    """The agent's active customers: overdue first, then due today, then by next due date."""
    customers = customer_list(Customer.objects.filter(assigned_agent=agent, is_active=True))
    priority = Case(
        When(overdue_amount__gt=0, then=Value(0)),
        When(due_today__gt=0, then=Value(1)),
        When(next_due_date__isnull=False, then=Value(2)),
        default=Value(3),
    )
    return customers.order_by(priority, F("next_due_date").asc(nulls_last=True), "full_name", "pk")
