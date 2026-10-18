from datetime import date

from django.db.models import (
    Count,
    DecimalField,
    Exists,
    F,
    IntegerField,
    OuterRef,
    Prefetch,
    Q,
    QuerySet,
    Subquery,
    Sum,
    Value,
)
from django.db.models.functions import Coalesce

from apps.collections.models import Allocation, Collection
from apps.core.dates import business_date
from apps.core.money import DECIMAL_PLACES, MAX_DIGITS, ZERO
from apps.payments.models import GatewayOrder

from .models import Installment, Loan

_MONEY = DecimalField(max_digits=MAX_DIGITS, decimal_places=DECIMAL_PLACES)
_UNPAID = ~Q(status=Installment.Status.PAID)


def _per_loan(installments: QuerySet[Installment], aggregate, output_field) -> Subquery:
    """Aggregate over one loan's installments as a correlated subquery (no outer GROUP BY)."""
    return Subquery(
        installments.filter(loan=OuterRef("pk"))
        .order_by()
        .values("loan")
        .annotate(value=aggregate)
        .values("value"),
        output_field=output_field,
    )


def _repayment_activity() -> Exists:
    return Exists(Collection.objects.filter(loan=OuterRef("pk"))) | Exists(
        GatewayOrder.objects.filter(loan=OuterRef("pk"))
    )


def loans_with_balances(
    queryset: QuerySet[Loan] | None = None, *, today: date | None = None
) -> QuerySet[Loan]:
    """Loans annotated with `overdue_amount`, `paid_installments`, `next_due_*` and `terms_locked`.

    Overdue means an installment past its due date that is not fully paid.
    """
    today = today or business_date()
    queryset = Loan.objects.all() if queryset is None else queryset
    next_due = Installment.objects.filter(_UNPAID, loan=OuterRef("pk")).order_by("installment_no")
    return queryset.select_related("customer__assigned_agent", "branch").annotate(
        overdue_amount=Coalesce(
            _per_loan(
                Installment.objects.filter(_UNPAID, due_date__lt=today),
                Sum(F("amount_due") - F("amount_paid")),
                _MONEY,
            ),
            Value(ZERO),
            output_field=_MONEY,
        ),
        paid_installments=Coalesce(
            _per_loan(
                Installment.objects.filter(status=Installment.Status.PAID),
                Count("pk"),
                IntegerField(),
            ),
            Value(0),
        ),
        next_due_installment_no=Subquery(next_due.values("installment_no")[:1]),
        next_due_date=Subquery(next_due.values("due_date")[:1]),
        next_due_amount=Subquery(
            next_due.annotate(balance=F("amount_due") - F("amount_paid")).values("balance")[:1],
            output_field=_MONEY,
        ),
        terms_locked=_repayment_activity(),
    )


def get_loan(pk: int) -> Loan:
    return loans_with_balances().get(pk=pk)


def has_repayment_activity(loan: Loan) -> bool:
    """Any collection (even a voided one) or UPI order freezes the loan's terms."""
    return loan.collections.exists() or loan.gateway_orders.exists()


def loan_schedule(loan: Loan) -> QuerySet[Installment]:
    return loan.installments.order_by("installment_no")


def loan_repayments(loan: Loan) -> QuerySet[Collection]:
    """Every collection on the loan, newest first, including voided ones."""
    return (
        Collection.objects.filter(loan=loan)
        .select_related("agent", "submission", "deposit")
        .prefetch_related(
            Prefetch(
                "allocations",
                queryset=Allocation.objects.select_related("installment").order_by(
                    "installment__installment_no"
                ),
            )
        )
        .order_by("-collected_at", "-pk")
    )
