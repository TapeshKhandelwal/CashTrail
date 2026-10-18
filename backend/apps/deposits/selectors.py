from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db.models import Count, Prefetch, QuerySet, Sum, Value
from django.db.models.functions import Coalesce

from apps.accounts.models import User
from apps.accounts.scoping import scope_queryset
from apps.audit.models import AuditAction, AuditLog
from apps.collections.models import Collection
from apps.core.dates import day_bounds
from apps.core.money import ZERO
from apps.reconciliation.models import CashSubmission, Discrepancy

from .models import BankAccount, BankDeposit


def bank_accounts() -> QuerySet[BankAccount]:
    return BankAccount.objects.all()


def deposits() -> QuerySet[BankDeposit]:
    return BankDeposit.objects.select_related(
        "branch", "bank_account", "created_by", "settled_by", "failed_by"
    )


def deposit_details() -> QuerySet[BankDeposit]:
    """Deposits with everything the reconciliation view shows, in a fixed number of queries."""
    return (
        deposits()
        .annotate(collections_count=Count("collections"))
        .prefetch_related(
            Prefetch(
                "submissions",
                queryset=CashSubmission.objects.select_related("agent", "reviewed_by").order_by(
                    "pk"
                ),
            ),
            Prefetch("discrepancies", queryset=Discrepancy.objects.order_by("created_at")),
        )
    )


def deposited_submission_ids(deposit: BankDeposit) -> list[int]:
    """The submissions `deposit` carried; a failed deposit released them, so its trail says."""
    if deposit.status != BankDeposit.Status.FAILED:
        return sorted(deposit.submissions.values_list("pk", flat=True))
    return sorted(_recorded(deposit, AuditAction.DEPOSIT_CREATED).get("submission_ids", []))


def settlement_selection(settlement: BankDeposit) -> tuple[list[int] | None, date | None]:
    """How the payments in a gateway settlement were selected: `(collection_ids, up_to_date)`."""
    requested = _recorded(settlement, AuditAction.GATEWAY_SETTLEMENT_RECORDED).get("requested", {})
    up_to_date = requested.get("up_to_date")
    return requested.get("collection_ids"), date.fromisoformat(up_to_date) if up_to_date else None


def _recorded(deposit: BankDeposit, action: AuditAction) -> dict:
    entry = (
        AuditLog.objects.filter(
            action=action, entity_type=BankDeposit._meta.model_name, entity_id=str(deposit.pk)
        )
        .values_list("after", flat=True)
        .first()
    )
    return entry or {}


def gateway_settlements() -> QuerySet[BankDeposit]:
    return deposits().filter(source=BankDeposit.Source.GATEWAY)


@dataclass(frozen=True)
class PendingTotal:
    count: int
    total_amount: Decimal


def _totals(queryset: QuerySet, amount_field: str) -> PendingTotal:
    totals = queryset.order_by().aggregate(
        count=Count("pk"), total_amount=Coalesce(Sum(amount_field), Value(ZERO))
    )
    return PendingTotal(**totals)


def pending_cash_submissions(user: User, branch_id: int | None = None) -> QuerySet[CashSubmission]:
    """Approved cash sitting at the branch, not yet carried by a bank deposit."""
    queryset = scope_queryset(
        CashSubmission.objects.filter(
            status__in=CashSubmission.APPROVED_STATUSES, deposit__isnull=True
        ),
        user,
    )
    if branch_id is not None:
        queryset = queryset.filter(branch_id=branch_id)
    return queryset.select_related("agent", "branch", "reviewed_by").order_by("reviewed_at", "pk")


def pending_cash_total(submissions: QuerySet[CashSubmission]) -> PendingTotal:
    return _totals(submissions, "received_amount")


def unsettled_upi_collections(up_to_date: date | None = None) -> QuerySet[Collection]:
    """Captured UPI payments not yet covered by a gateway settlement."""
    queryset = Collection.objects.filter(
        mode=Collection.Mode.UPI, status=Collection.Status.COLLECTED
    )
    if up_to_date is not None:
        queryset = queryset.filter(collected_at__lt=day_bounds(up_to_date)[1])
    return queryset.select_related("branch", "loan", "customer").order_by("collected_at", "pk")


def unsettled_upi_total(collections: QuerySet[Collection]) -> PendingTotal:
    return _totals(collections, "amount")
