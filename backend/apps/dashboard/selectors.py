"""Read-only aggregates behind the dashboards and CSV reports.

Every queryset is narrowed to the viewer's role scope first and only then by the
requested branch/agent, so a filter can never widen what a user may see. KPIs are
computed with conditional aggregation: one query per source table, whatever the
number of metrics or rows.

The receipt status filter narrows every figure made of receipts: collected, voided, settled,
where the cash is now (with agents, awaiting count, at branch, in the bank), the trend and
the lifecycle. Dues, loans, cash counted or deposited in the period, and discrepancies are
not receipts in one status, so they ignore it.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.db.models import Avg, Count, Exists, F, Min, OuterRef, Q, QuerySet, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.scoping import scope_queryset
from apps.branches.models import Branch
from apps.collections.metrics import (
    CASH,
    CASH_AGEING_BUCKETS,
    CASH_AWAITING_REVIEW,
    CASH_IN_HAND,
    NOT_VOIDED,
    UPI,
    held_between,
    settled_between,
)
from apps.collections.models import Collection
from apps.core.dates import business_date, day_bounds
from apps.core.money import ZERO, money_sum
from apps.deposits.models import BankDeposit, delayed_q
from apps.loans.models import Installment, Loan
from apps.reconciliation.models import CashSubmission, Discrepancy

PERCENT = Decimal("0.01")
ONE_DAY_IN_MICROSECONDS = Decimal(86_400_000_000)
# A condition no row meets: keeps a figure at zero when the status filter rules it out.
NO_ROWS = Q(pk__isnull=True)

# A settled UPI receipt skipped the branch and bank-deposit steps, so it counts towards
# every stage it bypassed; this keeps the funnel monotonic across both modes.
LIFECYCLE_STAGES = (
    ("COLLECTED", "Collected", ~Q(status=Collection.Status.VOIDED)),
    (
        "BRANCH_RECEIVED",
        "Received at branch",
        Q(
            status__in=[
                Collection.Status.BRANCH_RECEIVED,
                Collection.Status.DEPOSITED,
                Collection.Status.SETTLED,
            ]
        ),
    ),
    (
        "DEPOSITED",
        "Deposited in bank",
        Q(status__in=[Collection.Status.DEPOSITED, Collection.Status.SETTLED]),
    ),
    ("SETTLED", "Settled", Q(status=Collection.Status.SETTLED)),
)


@dataclass(frozen=True)
class DashboardFilters:
    date_from: date
    date_to: date
    branch: Branch | None = None
    agent: User | None = None
    status: str = ""

    @property
    def dates(self) -> tuple[date, date]:
        return self.date_from, self.date_to

    @property
    def moments(self) -> tuple[datetime, datetime]:
        """Aware [start, end) covering the whole date range in the business timezone."""
        return day_bounds(self.date_from)[0], day_bounds(self.date_to)[1]


# Visibility -------------------------------------------------------------------------


def visible_branches(user) -> QuerySet[Branch]:
    if user.has_global_scope:
        return Branch.objects.all()
    return Branch.objects.filter(pk=user.branch_id)


def visible_agents(user) -> QuerySet[User]:
    agents = User.objects.filter(role=User.Role.AGENT)
    if user.has_global_scope:
        return agents
    if user.is_branch_manager:
        return agents.filter(branch_id=user.branch_id)
    return agents.filter(pk=user.pk)


def _narrow(
    queryset: QuerySet,
    user,
    filters: DashboardFilters,
    *,
    branch_field: str = "branch",
    agent_field: str = "agent",
) -> QuerySet:
    queryset = scope_queryset(queryset, user, branch_field=branch_field, agent_field=agent_field)
    if filters.branch is not None:
        queryset = queryset.filter(**{branch_field: filters.branch})
    if filters.agent is not None:
        queryset = queryset.filter(**{agent_field: filters.agent})
    return queryset


def scoped_installments(user, filters: DashboardFilters) -> QuerySet[Installment]:
    return _narrow(
        Installment.objects.all(),
        user,
        filters,
        branch_field="loan__branch",
        agent_field="loan__customer__assigned_agent",
    )


def scoped_loans(user, filters: DashboardFilters) -> QuerySet[Loan]:
    return _narrow(Loan.objects.all(), user, filters, agent_field="customer__assigned_agent")


def scoped_collections(user, filters: DashboardFilters) -> QuerySet[Collection]:
    return _narrow(Collection.objects.all(), user, filters)


def scoped_submissions(user, filters: DashboardFilters) -> QuerySet[CashSubmission]:
    return _narrow(CashSubmission.objects.all(), user, filters)


def scoped_discrepancies(user, filters: DashboardFilters) -> QuerySet[Discrepancy]:
    return _narrow(Discrepancy.objects.all(), user, filters)


def _carries_receipts_of(agent) -> Exists:
    return Exists(Collection.objects.filter(deposit=OuterRef("pk"), agent=agent))


def scoped_deposits(user, filters: DashboardFilters) -> QuerySet[BankDeposit]:
    """Deposits have no agent of their own: for agents they are the deposits carrying
    the agent's receipts. A failed deposit releases its receipts, so it drops out."""
    deposits = BankDeposit.objects.all()
    if user.is_agent:
        deposits = deposits.filter(_carries_receipts_of(user))
    else:
        deposits = scope_queryset(deposits, user)
    if filters.branch is not None:
        deposits = deposits.filter(branch=filters.branch)
    if filters.agent is not None:
        deposits = deposits.filter(_carries_receipts_of(filters.agent))
    return deposits


# Metric definitions -----------------------------------------------------------------


@dataclass(frozen=True)
class Metrics:
    """Conditional aggregates over one table, plus `rows`: the OR of their conditions.

    Applying `rows` as a WHERE clause lets the indexes narrow the scan; the FILTER clauses
    alone would read every row in scope from all time.
    """

    aggregates: dict[str, Any]
    rows: Q

    def over(self, queryset: QuerySet) -> dict[str, Any]:
        return queryset.filter(self.rows).aggregate(**self.aggregates)


def _within(field: str, filters: DashboardFilters) -> Q:
    start, end = filters.moments
    return Q(**{f"{field}__gte": start, f"{field}__lt": end})


def _on_dates(field: str, filters: DashboardFilters) -> Q:
    return Q(**{f"{field}__range": filters.dates})


def _receipt_status(filters: DashboardFilters) -> Q:
    """Receipts in the chosen status; every receipt when none is chosen."""
    return Q(status=filters.status) if filters.status else Q()


def _at_stage(filters: DashboardFilters, status: str) -> Q:
    """For figures read off hand-overs or deposits, whose receipts all sit in `status`: the
    status filter either keeps the figure whole or rules it out."""
    return Q() if filters.status in ("", status) else NO_ROWS


def _tally(name: str, amount: str | F, condition: Q) -> dict[str, Any]:
    return {
        f"{name}_amount": money_sum(amount, condition),
        f"{name}_count": Count("pk", filter=condition),
    }


def _installment_metrics(filters: DashboardFilters, today: date) -> Metrics:
    due = _on_dates("due_date", filters)
    unpaid_past_due = Q(due_date__lt=today) & ~Q(status=Installment.Status.PAID)
    return Metrics(
        {
            **_tally("expected", "amount_due", due),
            **_tally(
                "overdue",
                F("amount_due") - F("amount_paid"),
                unpaid_past_due & Q(loan__status=Loan.Status.ACTIVE),
            ),
        },
        rows=due | unpaid_past_due,
    )


def _collection_metrics(filters: DashboardFilters, now: datetime) -> Metrics:
    in_period = _within("collected_at", filters)
    status = _receipt_status(filters)
    collected = in_period & NOT_VOIDED & status
    in_hand = CASH_IN_HAND & status
    aggregates = {
        **_tally("collected", "amount", collected),
        **_tally("collected_cash", "amount", collected & CASH),
        **_tally("collected_upi", "amount", collected & UPI),
        **_tally("voided", "amount", in_period & Q(status=Collection.Status.VOIDED) & status),
        **_tally("cash_with_agents", "amount", in_hand),
        **_tally("pending_verification", "amount", CASH_AWAITING_REVIEW & status),
        "oldest_cash_held_at": Min("collected_at", filter=in_hand),
    }
    for key, _, min_days, max_days in CASH_AGEING_BUCKETS:
        aged = held_between(now, min_days, max_days) & status
        aggregates |= _tally(f"ageing_{key}", "amount", aged)
    return Metrics(aggregates, rows=in_period | CASH_IN_HAND | CASH_AWAITING_REVIEW)


def _settlement_metrics(filters: DashboardFilters) -> Metrics:
    settled = settled_between(*filters.dates) & _receipt_status(filters)
    return Metrics(_tally("settled", "amount", Q()), rows=settled)


def _submission_metrics(filters: DashboardFilters) -> Metrics:
    approved = Q(status__in=CashSubmission.APPROVED_STATUSES)
    reviewed = _within("reviewed_at", filters)
    undeposited = approved & Q(deposit__isnull=True)
    return Metrics(
        {
            **_tally("branch_received", "received_amount", approved & reviewed),
            **_tally(
                "at_branch",
                "received_amount",
                undeposited & _at_stage(filters, Collection.Status.BRANCH_RECEIVED),
            ),
            **_tally(
                "rejected", "expected_amount", reviewed & Q(status=CashSubmission.Status.REJECTED)
            ),
        },
        rows=reviewed | undeposited,
    )


def _deposit_metrics(filters: DashboardFilters, today: date) -> Metrics:
    """Branch cash deposits; gateway settlements carry UPI receipts, counted as settled."""
    deposited = _on_dates("deposit_date", filters)
    settled = Q(status__in=BankDeposit.SETTLED_STATUSES) & _on_dates("settled_on", filters)
    pending = Q(status=BankDeposit.Status.PENDING)
    # The live "in the bank" position: the receipts of a pending deposit are all DEPOSITED.
    awaiting_bank = _at_stage(filters, Collection.Status.DEPOSITED)
    # "banked": an aggregate alias may not shadow the `deposited_amount` field.
    aggregates = {
        **_tally("banked", "deposited_amount", deposited & ~Q(status=BankDeposit.Status.FAILED)),
        "credited_count": Count("pk", filter=settled),
        "credited_exact_count": Count("pk", filter=settled & Q(status=BankDeposit.Status.SETTLED)),
        "settlement_lag": Avg(F("settled_on") - F("deposit_date"), filter=settled),
        **_tally("pending", "deposited_amount", pending & awaiting_bank),
        **_tally("delayed", "deposited_amount", delayed_q(today) & awaiting_bank),
    }
    for status in BankDeposit.Status:
        aggregates |= _tally(f"deposits_{status}", "deposited_amount", deposited & Q(status=status))
    return Metrics(
        aggregates, rows=Q(source=BankDeposit.Source.CASH) & (deposited | settled | pending)
    )


def _loan_metrics() -> Metrics:
    active = Q(status=Loan.Status.ACTIVE)
    return Metrics(
        _tally("outstanding", F("total_payable") - F("amount_paid"), active), rows=active
    )


def _discrepancy_metrics(filters: DashboardFilters) -> Metrics:
    is_open = Q(status=Discrepancy.Status.OPEN)
    raised = _within("created_at", filters)
    resolved = ~is_open & _within("resolved_at", filters)
    aggregates = {
        **_tally("open", "amount", is_open),
        **_tally("raised", "amount", raised),
        **_tally("resolved", "amount", resolved),
    }
    for kind in Discrepancy.Kind:
        aggregates |= _tally(f"open_{kind}", "amount", is_open & Q(kind=kind))
    return Metrics(aggregates, rows=is_open | raised | resolved)


# Shaping ----------------------------------------------------------------------------


def _pick(row: dict[str, Any], name: str) -> dict[str, Any]:
    return {"amount": row[f"{name}_amount"], "count": row[f"{name}_count"]}


def _percent(part: Decimal | int, whole: Decimal | int) -> Decimal | None:
    if not whole:
        return None
    return (Decimal(part) * 100 / Decimal(whole)).quantize(PERCENT, rounding=ROUND_HALF_UP)


def _days(duration: timedelta | None) -> Decimal | None:
    if duration is None:
        return None
    microseconds = Decimal(duration // timedelta(microseconds=1))
    return (microseconds / ONE_DAY_IN_MICROSECONDS).quantize(Decimal("0.1"), ROUND_HALF_UP)


def _empty_row(metrics: dict[str, Any]) -> dict[str, Any]:
    """What a group with no rows aggregates to: zero amounts and counts, no extremes."""
    defaults = {}
    for name in metrics:
        if name.endswith("_amount"):
            defaults[name] = ZERO
        elif name.endswith("_count"):
            defaults[name] = 0
        else:
            defaults[name] = None
    return defaults


def _grouped(queryset: QuerySet, key: str, metrics: dict[str, Any]) -> dict[Any, dict]:
    rows = queryset.values(key).order_by().annotate(**metrics)
    return {row.pop(key): row for row in rows}


# Dashboards -------------------------------------------------------------------------


def dashboard_summary(user, filters: DashboardFilters, *, now: datetime | None = None) -> dict:
    now = now or timezone.now()
    today = business_date(now)
    dues = _installment_metrics(filters, today).over(scoped_installments(user, filters))
    receipts = _collection_metrics(filters, now).over(scoped_collections(user, filters))
    settled = _settlement_metrics(filters).over(scoped_collections(user, filters))
    submissions = _submission_metrics(filters).over(scoped_submissions(user, filters))
    deposits = _deposit_metrics(filters, today).over(scoped_deposits(user, filters))
    loans = _loan_metrics().over(scoped_loans(user, filters))
    discrepancies = _discrepancy_metrics(filters).over(scoped_discrepancies(user, filters))

    return {
        "date_from": filters.date_from,
        "date_to": filters.date_to,
        "expected": _pick(dues, "expected"),
        "collected": {
            **_pick(receipts, "collected"),
            "cash": _pick(receipts, "collected_cash"),
            "upi": _pick(receipts, "collected_upi"),
        },
        "voided": _pick(receipts, "voided"),
        "cash_with_agents": _pick(receipts, "cash_with_agents"),
        "pending_verification": _pick(receipts, "pending_verification"),
        "cash_ageing": [
            {"bucket": key, "label": label, **_pick(receipts, f"ageing_{key}")}
            for key, label, *_ in CASH_AGEING_BUCKETS
        ],
        "branch_received": _pick(submissions, "branch_received"),
        "at_branch": _pick(submissions, "at_branch"),
        "pending_deposits": _pick(deposits, "pending"),
        "deposits": {
            **_pick(deposits, "banked"),
            "by_status": [
                {"status": status, **_pick(deposits, f"deposits_{status}")}
                for status in BankDeposit.Status
            ],
        },
        "settled": _pick(settled, "settled"),
        "delayed_settlements": _pick(deposits, "delayed"),
        "outstanding": _pick(loans, "outstanding"),
        "overdue": _pick(dues, "overdue"),
        "discrepancies": {
            "open": _pick(discrepancies, "open"),
            "open_by_kind": [
                {"kind": kind, **_pick(discrepancies, f"open_{kind}")} for kind in Discrepancy.Kind
            ],
            "raised": _pick(discrepancies, "raised"),
            "resolved": _pick(discrepancies, "resolved"),
        },
        "collection_efficiency": _percent(receipts["collected_amount"], dues["expected_amount"]),
        "deposit_accuracy": _percent(deposits["credited_exact_count"], deposits["credited_count"]),
        "avg_settlement_lag_days": _days(deposits["settlement_lag"]),
    }


def collection_trend(user, filters: DashboardFilters) -> list[dict]:
    """Daily expected dues, receipts collected, and receipts settled (by bank credit date)."""
    business_tz = timezone.get_current_timezone()
    expected = dict(
        scoped_installments(user, filters)
        .filter(_on_dates("due_date", filters))
        .values_list("due_date")
        .order_by()
        .annotate(Sum("amount_due"))
    )
    status = _receipt_status(filters)
    collected = dict(
        scoped_collections(user, filters)
        .filter(_within("collected_at", filters) & NOT_VOIDED & status)
        .annotate(day=TruncDate("collected_at", tzinfo=business_tz))
        .values_list("day")
        .order_by()
        .annotate(Sum("amount"))
    )
    settled = dict(
        scoped_collections(user, filters)
        .filter(settled_between(*filters.dates) & status)
        .values_list("deposit__settled_on")
        .order_by()
        .annotate(Sum("amount"))
    )

    days = (filters.date_to - filters.date_from).days + 1
    return [
        {
            "date": day,
            "expected": expected.get(day, ZERO),
            "collected": collected.get(day, ZERO),
            "settled": settled.get(day, ZERO),
        }
        for day in (filters.date_from + timedelta(days=offset) for offset in range(days))
    ]


def collection_lifecycle(user, filters: DashboardFilters) -> dict:
    """Funnel of receipts collected in the period, by the furthest stage they reached."""
    dues = (
        scoped_installments(user, filters)
        .filter(_on_dates("due_date", filters))
        .aggregate(**_tally("expected", "amount_due", Q()))
    )
    receipts = scoped_collections(user, filters).filter(
        _within("collected_at", filters) & _receipt_status(filters)
    )
    metrics = {}
    for stage, _, condition in LIFECYCLE_STAGES:
        metrics |= _tally(f"stage_{stage}", "amount", condition)
    for status in Collection.Status:
        metrics |= _tally(f"status_{status}", "amount", Q(status=status))
    totals = receipts.aggregate(**metrics)

    return {
        "date_from": filters.date_from,
        "date_to": filters.date_to,
        "expected": _pick(dues, "expected"),
        "stages": [
            {"stage": stage, "label": label, **_pick(totals, f"stage_{stage}")}
            for stage, label, _ in LIFECYCLE_STAGES
        ],
        "by_status": [
            {"status": status, "label": status.label, **_pick(totals, f"status_{status}")}
            for status in Collection.Status
        ],
    }


def branches_for_breakdown(user, filters: DashboardFilters) -> QuerySet[Branch]:
    branches = visible_branches(user)
    if filters.branch is not None:
        branches = branches.filter(pk=filters.branch.pk)
    if filters.agent is not None:
        branches = branches.filter(pk=filters.agent.branch_id)
    return branches.order_by("code")


def branch_breakdown(
    user, filters: DashboardFilters, branches: Sequence[Branch], *, now: datetime | None = None
) -> list[dict]:
    """One row per branch; seven grouped queries regardless of how many branches are listed."""
    now = now or timezone.now()
    today = business_date(now)
    ids = [branch.pk for branch in branches]
    sources = (
        (
            scoped_installments(user, filters).filter(loan__branch__in=ids),
            "loan__branch",
            _installment_metrics(filters, today),
        ),
        (
            scoped_collections(user, filters).filter(branch__in=ids),
            "branch",
            _collection_metrics(filters, now),
        ),
        (
            scoped_collections(user, filters).filter(branch__in=ids),
            "branch",
            _settlement_metrics(filters),
        ),
        (
            scoped_submissions(user, filters).filter(branch__in=ids),
            "branch",
            _submission_metrics(filters),
        ),
        (
            scoped_deposits(user, filters).filter(branch__in=ids),
            "branch",
            _deposit_metrics(filters, today),
        ),
        (scoped_loans(user, filters).filter(branch__in=ids), "branch", _loan_metrics()),
        (
            scoped_discrepancies(user, filters).filter(branch__in=ids),
            "branch",
            _discrepancy_metrics(filters),
        ),
    )
    merged = _merge_groups(ids, sources)
    return [
        {
            "branch": branch,
            **_team_row(merged[branch.pk]),
            "at_branch": _pick(merged[branch.pk], "at_branch"),
            "deposited": _pick(merged[branch.pk], "banked"),
            "settled": _pick(merged[branch.pk], "settled"),
            "delayed_settlements": _pick(merged[branch.pk], "delayed"),
        }
        for branch in branches
    ]


def agents_for_breakdown(user, filters: DashboardFilters) -> QuerySet[User]:
    agents = visible_agents(user)
    if filters.branch is not None:
        agents = agents.filter(branch=filters.branch)
    if filters.agent is not None:
        agents = agents.filter(pk=filters.agent.pk)
    return agents.select_related("branch").order_by(
        "branch__code", "first_name", "last_name", "username"
    )


def agent_breakdown(
    user, filters: DashboardFilters, agents: Sequence[User], *, now: datetime | None = None
) -> list[dict]:
    """One row per agent: dues of assigned customers, cash in hand, hand-overs and shortages."""
    now = now or timezone.now()
    today = business_date(now)
    ids = [agent.pk for agent in agents]
    sources = (
        (
            scoped_installments(user, filters).filter(loan__customer__assigned_agent__in=ids),
            "loan__customer__assigned_agent",
            _installment_metrics(filters, today),
        ),
        (
            scoped_collections(user, filters).filter(agent__in=ids),
            "agent",
            _collection_metrics(filters, now),
        ),
        (
            scoped_submissions(user, filters).filter(agent__in=ids),
            "agent",
            _submission_metrics(filters),
        ),
        (
            scoped_loans(user, filters).filter(customer__assigned_agent__in=ids),
            "customer__assigned_agent",
            _loan_metrics(),
        ),
        (
            scoped_discrepancies(user, filters).filter(agent__in=ids),
            "agent",
            _discrepancy_metrics(filters),
        ),
    )
    merged = _merge_groups(ids, sources)
    return [
        {
            "agent": agent,
            **_team_row(merged[agent.pk]),
            "oldest_cash_held_at": merged[agent.pk]["oldest_cash_held_at"],
            "rejected_submissions": _pick(merged[agent.pk], "rejected"),
        }
        for agent in agents
    ]


def _merge_groups(
    ids: Iterable[int], sources: Iterable[tuple[QuerySet, str, Metrics]]
) -> dict[int, dict[str, Any]]:
    merged: dict[int, dict[str, Any]] = {pk: {} for pk in ids}
    for queryset, key, metrics in sources:
        groups = _grouped(queryset.filter(metrics.rows), key, metrics.aggregates)
        empty = _empty_row(metrics.aggregates)
        for pk, row in merged.items():
            row |= groups.get(pk, empty)
    return merged


def _team_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "expected": _pick(row, "expected"),
        "collected": _pick(row, "collected"),
        "cash_with_agents": _pick(row, "cash_with_agents"),
        "pending_verification": _pick(row, "pending_verification"),
        "branch_received": _pick(row, "branch_received"),
        "outstanding": _pick(row, "outstanding"),
        "overdue": _pick(row, "overdue"),
        "open_discrepancies": _pick(row, "open"),
        "collection_efficiency": _percent(row["collected_amount"], row["expected_amount"]),
    }


# Reports ----------------------------------------------------------------------------


def _with_status(queryset: QuerySet, filters: DashboardFilters) -> QuerySet:
    return queryset.filter(status=filters.status) if filters.status else queryset


def collections_report(user, filters: DashboardFilters) -> QuerySet[Collection]:
    rows = scoped_collections(user, filters).filter(_within("collected_at", filters))
    return (
        _with_status(rows, filters)
        .select_related("loan", "customer", "branch", "agent", "submission", "deposit")
        .order_by("collected_at", "pk")
    )


def submissions_report(user, filters: DashboardFilters) -> QuerySet[CashSubmission]:
    rows = scoped_submissions(user, filters).filter(_within("submitted_at", filters))
    return (
        _with_status(rows, filters)
        .select_related("branch", "agent", "reviewed_by", "deposit")
        .order_by("submitted_at", "pk")
    )


def deposits_report(user, filters: DashboardFilters) -> QuerySet[BankDeposit]:
    rows = scoped_deposits(user, filters).filter(_on_dates("deposit_date", filters))
    return (
        _with_status(rows, filters)
        .select_related("branch", "bank_account", "created_by", "settled_by")
        .order_by("deposit_date", "pk")
    )


def discrepancies_report(user, filters: DashboardFilters) -> QuerySet[Discrepancy]:
    rows = scoped_discrepancies(user, filters).filter(_within("created_at", filters))
    return (
        _with_status(rows, filters)
        .select_related("branch", "agent", "submission", "deposit", "raised_by", "resolved_by")
        .order_by("created_at", "pk")
    )
