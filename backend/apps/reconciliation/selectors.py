"""Read-side queries for submissions and discrepancies, and the reconciliation summaries.

Summaries aggregate in the database with one grouped query per source table, so their
cost does not grow with the number of branches or agents in scope.
"""

from datetime import date, datetime
from typing import Any

from django.db.models import Count, F, Min, Prefetch, Q, QuerySet
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
from apps.core.dates import day_bounds
from apps.core.money import ZERO, money_sum
from apps.deposits.models import BankDeposit, delayed_q
from apps.loans.models import Installment

from .models import CashSubmission, Discrepancy

APPROVED = Q(status__in=CashSubmission.APPROVED_STATUSES)
AGEING_METRICS = {
    "under_1_day": "held_under_1d",
    "1_to_2_days": "held_1_to_2d",
    "over_2_days": "held_over_2d",
}

BRANCH_MONEY_METRICS = (
    "expected_due",
    "collected_cash",
    "collected_upi",
    "collected_total",
    "held_by_agents",
    "pending_verification",
    "received_at_branch",
    "at_branch_not_deposited",
    "deposited",
    "pending_settlement",
    "settled_cash",
    "settled_upi",
    "settled_total",
    "open_shortage",
    "open_excess",
)
BRANCH_COUNT_METRICS = ("pending_submissions", "delayed_deposits", "open_discrepancies")

AGENT_MONEY_METRICS = (
    "collected_cash",
    "collected_upi",
    "submitted",
    "received",
    "cash_in_hand",
    "pending_verification",
    "held_under_1d",
    "held_1_to_2d",
    "held_over_2d",
    "open_shortage",
)
AGENT_COUNT_METRICS = ("collection_count", "receipts_in_hand")


def cash_submissions() -> QuerySet[CashSubmission]:
    return CashSubmission.objects.select_related(
        "agent", "branch", "reviewed_by", "deposit"
    ).annotate(collection_count=Count("items"))


def cash_submission_details() -> QuerySet[CashSubmission]:
    return cash_submissions().prefetch_related(
        Prefetch("discrepancies", queryset=Discrepancy.objects.order_by("created_at"))
    )


def submission_collections(submission: CashSubmission) -> QuerySet[Collection]:
    """Receipts handed over in `submission`, including those a rejection returned."""
    return (
        Collection.objects.filter(submission_items__submission=submission)
        .select_related("loan", "customer")
        .order_by("collected_at", "pk")
    )


def discrepancies() -> QuerySet[Discrepancy]:
    return Discrepancy.objects.select_related(
        "branch", "agent", "submission", "deposit", "raised_by", "resolved_by"
    )


def branch_summary(
    user, *, date_from: date, date_to: date, branch_id: int | None = None
) -> dict[str, Any]:
    """Per-branch reconciliation position for the period, plus totals.

    Flows (expected, collected, received, deposited, settled) are limited to the period;
    positions (held by agents, pending verification, at branch, pending settlement, open
    discrepancies) are as of now. Across all branches, the totals also count open
    discrepancies tied to no branch (gateway settlement mismatches), so they match the
    discrepancy list; no branch row carries those.
    """
    branches = scope_queryset(Branch.objects.order_by("code"), user, branch_field="pk")
    if branch_id is not None:
        branches = branches.filter(pk=branch_id)
    with_unassigned = branch_id is None and user.has_global_scope
    unassigned: dict[str, Any] = {}
    rows = {
        branch["id"]: {
            "branch_id": branch["id"],
            "branch_code": branch["code"],
            "branch_name": branch["name"],
            **dict.fromkeys(BRANCH_MONEY_METRICS, ZERO),
            **dict.fromkeys(BRANCH_COUNT_METRICS, 0),
        }
        for branch in branches.values("id", "code", "name")
    }
    if rows:
        start, end = _period_bounds(date_from, date_to)
        for key, values in _branch_aggregates(
            list(rows), date_from, date_to, start, end, with_unassigned=with_unassigned
        ):
            if key is None:
                unassigned = values
            else:
                rows[key].update(values)
        for row in rows.values():
            row["collected_total"] = row["collected_cash"] + row["collected_upi"]
            row["settled_total"] = row["settled_cash"] + row["settled_upi"]

    branch_rows = list(rows.values())
    totals = _totals(branch_rows, BRANCH_MONEY_METRICS, BRANCH_COUNT_METRICS)
    for name, value in unassigned.items():
        totals[name] += value
    return {
        "date_from": date_from,
        "date_to": date_to,
        "totals": totals,
        "branches": branch_rows,
    }


def agents_summary(
    user,
    *,
    date_from: date,
    date_to: date,
    branch_id: int | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Per-agent collections and hand-overs for the period, with cash-in-hand ageing as of now.

    Inactive agents are listed only while they still hold cash.
    """
    now = now or timezone.now()
    start, end = _period_bounds(date_from, date_to)
    agents = User.objects.filter(role=User.Role.AGENT)
    agents = agents.filter(pk=user.pk) if user.is_agent else scope_queryset(agents, user)
    if branch_id is not None:
        agents = agents.filter(branch_id=branch_id)

    stats: dict[int, dict[str, Any]] = {}
    for key, values in _agent_aggregates(agents, start, end, now):
        stats.setdefault(key, {}).update(values)

    holding = [pk for pk, values in stats.items() if values.get("cash_in_hand")]
    rows = []
    for agent in (
        agents.filter(Q(is_active=True) | Q(pk__in=holding))
        .select_related("branch")
        .order_by("branch__code", "first_name", "last_name", "username")
    ):
        row = {
            "agent_id": agent.pk,
            "username": agent.username,
            "full_name": agent.get_full_name() or agent.username,
            "branch_id": agent.branch_id,
            "branch_code": agent.branch.code if agent.branch_id else None,
            **dict.fromkeys(AGENT_MONEY_METRICS, ZERO),
            **dict.fromkeys(AGENT_COUNT_METRICS, 0),
            "oldest_held_at": None,
            **stats.get(agent.pk, {}),
        }
        oldest = row["oldest_held_at"]
        row["oldest_held_hours"] = int((now - oldest).total_seconds() // 3600) if oldest else None
        rows.append(row)

    return {
        "date_from": date_from,
        "date_to": date_to,
        "as_of": now,
        "totals": _totals(rows, AGENT_MONEY_METRICS, AGENT_COUNT_METRICS),
        "agents": rows,
    }


def _branch_aggregates(
    branch_ids: list[int], date_from, date_to, start, end, *, with_unassigned: bool = False
):
    """Yield `(branch_id, {metric: value})` from one grouped query per source table.

    With `with_unassigned`, open discrepancies tied to no branch come back under `None`.
    """
    collected = Q(collected_at__gte=start, collected_at__lt=end) & NOT_VOIDED
    settled = settled_between(date_from, date_to)
    reviewed = Q(reviewed_at__gte=start, reviewed_at__lt=end)
    awaiting_review = Q(status=CashSubmission.Status.SUBMITTED)
    pending = Q(status=BankDeposit.Status.PENDING)
    deposited = Q(deposit_date__gte=date_from, deposit_date__lte=date_to) & ~Q(
        status=BankDeposit.Status.FAILED
    )
    open_items = Q(status=Discrepancy.Status.OPEN)
    discrepancy_branches = Q(branch__in=branch_ids)
    if with_unassigned:
        discrepancy_branches |= Q(branch__isnull=True)

    queries = (
        Installment.objects.filter(
            loan__branch__in=branch_ids, due_date__gte=date_from, due_date__lte=date_to
        )
        .values(key=F("loan__branch"))
        .annotate(expected_due=money_sum("amount_due")),
        Collection.objects.filter(branch__in=branch_ids)
        .filter(collected | CASH_IN_HAND | CASH_AWAITING_REVIEW)
        .values(key=F("branch"))
        .annotate(
            collected_cash=money_sum("amount", collected & CASH),
            collected_upi=money_sum("amount", collected & UPI),
            held_by_agents=money_sum("amount", CASH_IN_HAND),
            pending_verification=money_sum("amount", CASH_AWAITING_REVIEW),
        ),
        Collection.objects.filter(branch__in=branch_ids)
        .filter(settled)
        .values(key=F("branch"))
        .annotate(
            settled_cash=money_sum("amount", CASH),
            settled_upi=money_sum("amount", UPI),
        ),
        CashSubmission.objects.filter(branch__in=branch_ids)
        .filter(awaiting_review | (APPROVED & (reviewed | Q(deposit=None))))
        .values(key=F("branch"))
        .annotate(
            pending_submissions=Count("pk", filter=awaiting_review),
            received_at_branch=money_sum("received_amount", APPROVED & reviewed),
            at_branch_not_deposited=money_sum("received_amount", APPROVED & Q(deposit=None)),
        ),
        BankDeposit.objects.filter(branch__in=branch_ids, source=BankDeposit.Source.CASH)
        .filter(deposited | pending)
        .values(key=F("branch"))
        .annotate(
            deposited=money_sum("deposited_amount", deposited),
            pending_settlement=money_sum("deposited_amount", pending),
            delayed_deposits=Count("pk", filter=delayed_q()),
        ),
        Discrepancy.objects.filter(discrepancy_branches)
        .filter(open_items)
        .values(key=F("branch"))
        .annotate(
            open_discrepancies=Count("pk"),
            open_shortage=money_sum("amount", Q(direction=Discrepancy.Direction.SHORT)),
            open_excess=money_sum("amount", Q(direction=Discrepancy.Direction.EXCESS)),
        ),
    )
    for query in queries:
        for row in query.order_by():
            yield row.pop("key"), row


def _agent_aggregates(agents: QuerySet, start, end, now):
    """Yield `(agent_id, {metric: value})` from one grouped query per source table."""
    collected = Q(collected_at__gte=start, collected_at__lt=end) & NOT_VOIDED
    submitted = Q(submitted_at__gte=start, submitted_at__lt=end) & ~Q(
        status=CashSubmission.Status.REJECTED
    )
    reviewed = APPROVED & Q(reviewed_at__gte=start, reviewed_at__lt=end)
    open_shortage = Q(status=Discrepancy.Status.OPEN, direction=Discrepancy.Direction.SHORT)

    queries = (
        Collection.objects.filter(agent__in=agents)
        .filter(collected | CASH_IN_HAND | CASH_AWAITING_REVIEW)
        .values(key=F("agent"))
        .annotate(
            collected_cash=money_sum("amount", collected & CASH),
            collected_upi=money_sum("amount", collected & UPI),
            collection_count=Count("pk", filter=collected),
            cash_in_hand=money_sum("amount", CASH_IN_HAND),
            receipts_in_hand=Count("pk", filter=CASH_IN_HAND),
            pending_verification=money_sum("amount", CASH_AWAITING_REVIEW),
            oldest_held_at=Min("collected_at", filter=CASH_IN_HAND),
            **{
                AGEING_METRICS[key]: money_sum("amount", held_between(now, min_days, max_days))
                for key, _, min_days, max_days in CASH_AGEING_BUCKETS
            },
        ),
        CashSubmission.objects.filter(agent__in=agents)
        .filter(submitted | reviewed)
        .values(key=F("agent"))
        .annotate(
            submitted=money_sum("expected_amount", submitted),
            received=money_sum("received_amount", reviewed),
        ),
        Discrepancy.objects.filter(agent__in=agents)
        .filter(open_shortage)
        .values(key=F("agent"))
        .annotate(open_shortage=money_sum("amount")),
    )
    for query in queries:
        for row in query.order_by():
            yield row.pop("key"), row


def _period_bounds(date_from: date, date_to: date) -> tuple[datetime, datetime]:
    return day_bounds(date_from)[0], day_bounds(date_to)[1]


def _totals(rows: list[dict], money: tuple[str, ...], counts: tuple[str, ...]) -> dict[str, Any]:
    totals: dict[str, Any] = {name: sum((row[name] for row in rows), ZERO) for name in money}
    totals.update({name: sum(row[name] for row in rows) for name in counts})
    return totals
