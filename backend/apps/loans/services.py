"""Loan origination and changes to loan terms.

Repayments move `amount_paid` on loans and installments; that happens in the
collections services, never here.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from dateutil.relativedelta import relativedelta
from django.db import transaction
from django.utils import timezone

from apps.accounts.scoping import scope_queryset
from apps.audit.models import AuditAction
from apps.audit.services import log_event, snapshot
from apps.core.dates import business_date
from apps.core.exceptions import RecordLocked, ResourceNotFound, ScopeViolation, ValidationFailed
from apps.core.money import MAX_AMOUNT, ZERO
from apps.core.numbering import loan_number
from apps.customers.models import Customer

from .models import Installment, Loan
from .schedule import ScheduleRow, generate_schedule
from .selectors import has_repayment_activity

MAX_ANNUAL_RATE = Decimal("100")

TERM_FIELDS = (
    "principal",
    "annual_interest_rate",
    "tenure_months",
    "disbursed_on",
    "first_due_date",
)
_AUDITED_FIELDS = (*TERM_FIELDS, "emi_amount", "total_payable")
_SCHEDULE_FIELDS = ("due_date", "principal_component", "interest_component", "amount_due")


@dataclass(frozen=True, slots=True)
class LoanSchedule:
    principal: Decimal
    annual_interest_rate: Decimal
    tenure_months: int
    disbursed_on: date
    first_due_date: date
    rows: list[ScheduleRow]

    @property
    def emi_amount(self) -> Decimal:
        return self.rows[0].amount_due

    @property
    def total_payable(self) -> Decimal:
        return sum((row.amount_due for row in self.rows), ZERO)

    @property
    def total_interest(self) -> Decimal:
        return self.total_payable - self.principal


def build_schedule(
    *,
    principal: Decimal,
    annual_interest_rate: Decimal,
    tenure_months: int,
    disbursed_on: date | None = None,
    first_due_date: date | None = None,
) -> LoanSchedule:
    """Validate loan terms and compute the EMI schedule without touching the database.

    Disbursal defaults to today and the first EMI to one month after disbursal.
    """
    disbursed_on = disbursed_on or business_date()
    first_due_date = first_due_date or disbursed_on + relativedelta(months=1)
    if disbursed_on > business_date():
        raise ValidationFailed(
            "The disbursal date cannot be in the future.",
            details={"disbursed_on": disbursed_on.isoformat()},
        )
    if first_due_date <= disbursed_on:
        raise ValidationFailed(
            "The first EMI must fall due after the disbursal date.",
            details={
                "disbursed_on": disbursed_on.isoformat(),
                "first_due_date": first_due_date.isoformat(),
            },
        )
    if annual_interest_rate > MAX_ANNUAL_RATE:
        raise ValidationFailed(
            "The annual interest rate cannot exceed 100%.",
            details={"annual_interest_rate": str(annual_interest_rate)},
        )
    try:
        rows = generate_schedule(principal, annual_interest_rate, tenure_months, first_due_date)
    except ValueError as exc:
        raise ValidationFailed(str(exc)) from exc

    schedule = LoanSchedule(
        principal=principal,
        annual_interest_rate=annual_interest_rate,
        tenure_months=tenure_months,
        disbursed_on=disbursed_on,
        first_due_date=first_due_date,
        rows=rows,
    )
    if schedule.total_payable > MAX_AMOUNT:
        raise ValidationFailed(
            f"The total repayable cannot exceed {MAX_AMOUNT}; reduce the principal, rate or "
            "tenure.",
            details={"total_payable": str(schedule.total_payable)},
        )
    return schedule


def create_loan(
    actor,
    *,
    customer_id: int,
    principal: Decimal,
    annual_interest_rate: Decimal,
    tenure_months: int,
    disbursed_on: date | None = None,
    first_due_date: date | None = None,
) -> Loan:
    """Issue a loan to an active customer together with its full installment schedule."""
    if not (actor.is_admin or actor.is_branch_manager):
        raise ScopeViolation("Only admins and branch managers can create loans.")

    schedule = build_schedule(
        principal=principal,
        annual_interest_rate=annual_interest_rate,
        tenure_months=tenure_months,
        disbursed_on=disbursed_on,
        first_due_date=first_due_date,
    )

    with transaction.atomic():
        customers = scope_queryset(Customer.objects.select_related("branch"), actor)
        # Locking the customer keeps a concurrent deactivation from slipping past the check.
        customer = customers.select_for_update(of=("self",)).filter(pk=customer_id).first()
        if customer is None:
            raise ResourceNotFound("Customer not found.", details={"customer_id": customer_id})
        if not customer.is_active:
            raise ValidationFailed(
                "Loans cannot be issued to an inactive customer.",
                details={"customer_id": customer.pk},
            )
        if not customer.branch.is_active:
            raise ValidationFailed(
                "The customer's branch is inactive.",
                details={"branch": customer.branch.code},
            )

        loan = Loan.objects.create(
            loan_number=loan_number(customer.branch.code),
            customer=customer,
            branch=customer.branch,
            principal=schedule.principal,
            annual_interest_rate=schedule.annual_interest_rate,
            tenure_months=schedule.tenure_months,
            emi_amount=schedule.emi_amount,
            total_payable=schedule.total_payable,
            disbursed_on=schedule.disbursed_on,
            first_due_date=schedule.first_due_date,
            created_by=actor,
        )
        Installment.objects.bulk_create(
            Installment(
                loan=loan,
                installment_no=row.installment_no,
                due_date=row.due_date,
                principal_component=row.principal_component,
                interest_component=row.interest_component,
                amount_due=row.amount_due,
            )
            for row in schedule.rows
        )
        log_event(
            actor,
            AuditAction.LOAN_CREATED,
            loan,
            after=snapshot(loan, ("loan_number", "customer", "status", *_AUDITED_FIELDS)),
        )
    return loan


def update_loan_terms(actor, loan: Loan, **changes: Any) -> Loan:
    """Correct the terms of a loan that has no repayment activity yet.

    The schedule is recomputed and written over the existing installment rows,
    which are never deleted; that is also why the tenure cannot change.
    """
    unknown = changes.keys() - set(TERM_FIELDS)
    if unknown:
        raise TypeError(f"Not loan terms: {', '.join(sorted(unknown))}")

    with transaction.atomic():
        # Collections lock the loan row too, so the activity check below cannot race them.
        loan = Loan.objects.select_for_update().get(pk=loan.pk)
        _ensure_manages_branch(actor, loan.branch_id)

        changed = {name: value for name, value in changes.items() if getattr(loan, name) != value}
        if not changed:
            return loan
        if loan.is_closed or has_repayment_activity(loan):
            raise RecordLocked(
                "Loan terms cannot change once a repayment has been recorded.",
                details={"loan_number": loan.loan_number, "fields": sorted(changed)},
            )
        if "tenure_months" in changed:
            raise ValidationFailed(
                "The tenure cannot change once the schedule is issued.",
                details={"tenure_months": loan.tenure_months},
            )

        terms = {field: getattr(loan, field) for field in TERM_FIELDS} | changed
        schedule = build_schedule(**terms)

        installments = list(loan.installments.select_for_update().order_by("installment_no"))
        now = timezone.now()
        for installment, row in zip(installments, schedule.rows, strict=True):
            for field in _SCHEDULE_FIELDS:
                setattr(installment, field, getattr(row, field))
            installment.updated_at = now
        Installment.objects.bulk_update(installments, [*_SCHEDULE_FIELDS, "updated_at"])

        before = snapshot(loan, _AUDITED_FIELDS)
        for field, value in changed.items():
            setattr(loan, field, value)
        loan.emi_amount = schedule.emi_amount
        loan.total_payable = schedule.total_payable
        loan.save(update_fields=[*changed, "emi_amount", "total_payable", "updated_at"])
        log_event(
            actor,
            AuditAction.LOAN_UPDATED,
            loan,
            before=before,
            after=snapshot(loan, _AUDITED_FIELDS),
        )
    return loan


def _ensure_manages_branch(actor, branch_id: int) -> None:
    if actor.is_admin or (actor.is_branch_manager and actor.branch_id == branch_id):
        return
    raise ScopeViolation("You cannot manage loans of this branch.")
