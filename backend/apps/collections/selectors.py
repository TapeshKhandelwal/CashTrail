from datetime import date, datetime
from decimal import Decimal
from typing import TypedDict

from django.db.models import Count, Prefetch, Q, QuerySet

from apps.accounts.scoping import scope_queryset
from apps.core.dates import day_bounds
from apps.core.exceptions import ResourceNotFound
from apps.core.money import money_sum
from apps.loans.models import Loan

from .metrics import CASH, CASH_IN_HAND, NOT_VOIDED, UPI
from .models import Allocation, Collection

CASH_LIFECYCLE = (
    Collection.Status.COLLECTED,
    Collection.Status.SUBMITTED,
    Collection.Status.BRANCH_RECEIVED,
    Collection.Status.DEPOSITED,
    Collection.Status.SETTLED,
)
UPI_LIFECYCLE = (Collection.Status.COLLECTED, Collection.Status.SETTLED)


def collection_list_queryset() -> QuerySet[Collection]:
    return Collection.objects.select_related("loan", "customer", "branch", "agent")


def with_receipt_details(collections: QuerySet[Collection]) -> QuerySet[Collection]:
    return collections.select_related("submission", "deposit", "voided_by").prefetch_related(
        Prefetch("allocations", queryset=Allocation.objects.select_related("installment"))
    )


def get_collectable_loan(user, loan_id: int) -> Loan:
    """The loan if `user` may see it; otherwise 404 so ids outside the scope leak nothing."""
    loan = (
        scope_queryset(Loan.objects.all(), user, agent_field="customer__assigned_agent")
        .filter(pk=loan_id)
        .first()
    )
    if loan is None:
        raise ResourceNotFound("Loan not found.", details={"loan_id": loan_id})
    return loan


class TimelineStep(TypedDict):
    status: str
    label: str
    reached: bool
    at: datetime | None
    reference: str | None


def lifecycle_timeline(collection: Collection) -> list[TimelineStep]:
    """Where the money is on its way to the company account, one step per lifecycle stage."""
    submission_number = collection.submission.submission_number if collection.submission else None
    deposit_number = collection.deposit.deposit_number if collection.deposit else None
    stamps = {
        Collection.Status.COLLECTED: (collection.collected_at, collection.receipt_number),
        Collection.Status.SUBMITTED: (collection.submitted_at, submission_number),
        Collection.Status.BRANCH_RECEIVED: (collection.branch_received_at, submission_number),
        Collection.Status.DEPOSITED: (collection.deposited_at, deposit_number),
        Collection.Status.SETTLED: (collection.settled_at, deposit_number),
        Collection.Status.VOIDED: (collection.voided_at, None),
    }

    if collection.status == Collection.Status.VOIDED:
        stages = (Collection.Status.COLLECTED, Collection.Status.VOIDED)
    elif collection.mode == Collection.Mode.UPI:
        stages = UPI_LIFECYCLE
    else:
        stages = CASH_LIFECYCLE
    current = stages.index(collection.status)

    steps = []
    for index, stage in enumerate(stages):
        reached = index <= current
        at, reference = stamps[stage]
        steps.append(
            TimelineStep(
                status=stage,
                label=stage.label,
                reached=reached,
                at=at if reached else None,
                reference=reference if reached else None,
            )
        )
    return steps


class DailySummary(TypedDict):
    date: date
    count: int
    total_amount: Decimal
    cash_count: int
    cash_amount: Decimal
    upi_count: int
    upi_amount: Decimal
    voided_count: int
    unsubmitted_count: int
    unsubmitted_cash: Decimal


def daily_summary(collections: QuerySet[Collection], day: date) -> DailySummary:
    """Totals for one business day plus the cash still in agents' hands (from any day).

    `collections` must already be scoped to what the caller may see.
    """
    start, end = day_bounds(day)
    on_day = Q(collected_at__gte=start, collected_at__lt=end)
    live = on_day & NOT_VOIDED

    totals = collections.filter(on_day | CASH_IN_HAND).aggregate(
        count=Count("pk", filter=live),
        total_amount=money_sum("amount", live),
        cash_count=Count("pk", filter=live & CASH),
        cash_amount=money_sum("amount", live & CASH),
        upi_count=Count("pk", filter=live & UPI),
        upi_amount=money_sum("amount", live & UPI),
        voided_count=Count("pk", filter=on_day & Q(status=Collection.Status.VOIDED)),
        unsubmitted_count=Count("pk", filter=CASH_IN_HAND),
        unsubmitted_cash=money_sum("amount", CASH_IN_HAND),
    )
    return DailySummary(date=day, **totals)
