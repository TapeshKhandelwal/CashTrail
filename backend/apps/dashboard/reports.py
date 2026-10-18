"""CSV exports, streamed row by row so a large date range never sits in memory."""

import csv
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from django.db.models import QuerySet
from django.utils import timezone

from . import selectors
from .selectors import DashboardFilters

# Spreadsheet apps execute cells starting with these as formulas.
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


@dataclass(frozen=True)
class Column:
    header: str
    value: Callable[[Any], Any]


@dataclass(frozen=True)
class Report:
    name: str
    columns: tuple[Column, ...]
    rows: Callable[[Any, DashboardFilters], QuerySet]


def _cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return timezone.localtime(value).isoformat(timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, str) and value.startswith(FORMULA_PREFIXES):
        return f"'{value}"
    return value


class _Echo:
    """File-like sink that hands each formatted line straight back to the generator."""

    def write(self, value: str) -> str:
        return value


def stream_csv(columns: Iterable[Column], rows: Iterable[Any]) -> Iterator[str]:
    columns = tuple(columns)
    writer = csv.writer(_Echo())
    yield writer.writerow([column.header for column in columns])
    for row in rows:
        yield writer.writerow([_cell(column.value(row)) for column in columns])


def _username(user) -> str:
    return user.username if user else ""


def _number(document, attribute: str) -> str:
    return getattr(document, attribute) if document else ""


COLLECTIONS = Report(
    name="collections",
    rows=selectors.collections_report,
    columns=(
        Column("Receipt number", lambda c: c.receipt_number),
        Column("Collected at", lambda c: c.collected_at),
        Column("Mode", lambda c: c.mode),
        Column("Status", lambda c: c.status),
        Column("Amount", lambda c: c.amount),
        Column("Loan number", lambda c: c.loan.loan_number),
        Column("Customer code", lambda c: c.customer.customer_code),
        Column("Customer name", lambda c: c.customer.full_name),
        Column("Branch", lambda c: c.branch.code),
        Column("Agent", lambda c: _username(c.agent)),
        Column("Submission number", lambda c: _number(c.submission, "submission_number")),
        Column("Deposit number", lambda c: _number(c.deposit, "deposit_number")),
        Column("Gateway payment ID", lambda c: c.gateway_payment_id),
        Column("Submitted at", lambda c: c.submitted_at),
        Column("Branch received at", lambda c: c.branch_received_at),
        Column("Deposited at", lambda c: c.deposited_at),
        Column("Settled at", lambda c: c.settled_at),
        Column("Voided at", lambda c: c.voided_at),
        Column("Void reason", lambda c: c.void_reason),
        Column("Remarks", lambda c: c.remarks),
    ),
)

SUBMISSIONS = Report(
    name="submissions",
    rows=selectors.submissions_report,
    columns=(
        Column("Submission number", lambda s: s.submission_number),
        Column("Submitted at", lambda s: s.submitted_at),
        Column("Status", lambda s: s.status),
        Column("Branch", lambda s: s.branch.code),
        Column("Agent", lambda s: s.agent.username),
        Column("Expected amount", lambda s: s.expected_amount),
        Column("Declared amount", lambda s: s.declared_amount),
        Column("Received amount", lambda s: s.received_amount),
        Column("Difference", lambda s: s.difference),
        Column("Reviewed at", lambda s: s.reviewed_at),
        Column("Reviewed by", lambda s: _username(s.reviewed_by)),
        Column("Deposit number", lambda s: _number(s.deposit, "deposit_number")),
        Column("Review remarks", lambda s: s.review_remarks),
        Column("Rejection reason", lambda s: s.rejection_reason),
    ),
)

DEPOSITS = Report(
    name="deposits",
    rows=selectors.deposits_report,
    columns=(
        Column("Deposit number", lambda d: d.deposit_number),
        Column("Source", lambda d: d.source),
        Column("Status", lambda d: d.status),
        Column("Branch", lambda d: d.branch.code if d.branch else ""),
        Column("Bank account", lambda d: str(d.bank_account)),
        Column("Reference number", lambda d: d.reference_number),
        Column("Deposit date", lambda d: d.deposit_date),
        Column("Expected amount", lambda d: d.expected_amount),
        Column("Deposited amount", lambda d: d.deposited_amount),
        Column("Fee", lambda d: d.fee_amount),
        Column("Tax", lambda d: d.tax_amount),
        Column("Settled amount", lambda d: d.settled_amount),
        Column("Settled on", lambda d: d.settled_on),
        Column("Settlement reference", lambda d: d.settlement_reference),
        Column("Days pending", lambda d: d.days_pending),
        Column("Delayed", lambda d: d.is_delayed),
        Column("Created by", lambda d: d.created_by.username),
        Column("Settled by", lambda d: _username(d.settled_by)),
        Column("Remarks", lambda d: d.remarks),
        Column("Failure reason", lambda d: d.failure_reason),
    ),
)

DISCREPANCIES = Report(
    name="discrepancies",
    rows=selectors.discrepancies_report,
    columns=(
        Column("ID", lambda d: d.pk),
        Column("Raised at", lambda d: d.created_at),
        Column("Kind", lambda d: d.kind),
        Column("Direction", lambda d: d.direction),
        Column("Amount", lambda d: d.amount),
        Column("Status", lambda d: d.status),
        Column("Reason code", lambda d: d.reason_code),
        Column("Branch", lambda d: d.branch.code if d.branch else ""),
        Column("Agent", lambda d: _username(d.agent)),
        Column("Submission number", lambda d: _number(d.submission, "submission_number")),
        Column("Deposit number", lambda d: _number(d.deposit, "deposit_number")),
        Column("Raised by", lambda d: _username(d.raised_by)),
        Column("Resolved by", lambda d: _username(d.resolved_by)),
        Column("Resolved at", lambda d: d.resolved_at),
        Column("Notes", lambda d: d.notes),
        Column("Resolution notes", lambda d: d.resolution_notes),
    ),
)
