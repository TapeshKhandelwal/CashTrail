from datetime import timedelta
from decimal import Decimal

import pytest

from apps.core.money import ZERO
from apps.core.testing import factories
from apps.customers.models import Customer
from apps.customers.selectors import agent_route, loan_summaries, with_dues

from .helpers import installments, pay

pytestmark = pytest.mark.django_db


def dues(customer) -> Customer:
    return with_dues(Customer.objects.filter(pk=customer.pk)).get()


def test_loan_due_today(customer, make_loan, today):
    loan = make_loan(customer, first_due_date=today)

    row = dues(customer)

    assert row.outstanding == loan.total_payable
    assert row.overdue_amount == ZERO
    assert row.due_today == loan.emi_amount
    assert row.next_due_date == today
    assert row.active_loans == 1


def test_partial_payment_reduces_overdue_balance(customer, make_loan, overdue_date):
    loan = make_loan(customer, first_due_date=overdue_date)
    first, second, *_ = installments(loan)
    pay(first, Decimal("1000.00"))

    row = dues(customer)

    assert row.overdue_amount == first.amount_due + second.amount_due - Decimal("1000.00")
    assert row.due_today == ZERO
    assert row.next_due_date == first.due_date
    assert row.outstanding == loan.total_payable - Decimal("1000.00")


def test_fully_paid_installments_move_next_due_date(customer, make_loan, overdue_date):
    loan = make_loan(customer, first_due_date=overdue_date)
    first, second, third, *_ = installments(loan)
    pay(first, first.amount_due)
    pay(second, second.amount_due)

    row = dues(customer)

    assert row.overdue_amount == ZERO
    assert row.next_due_date == third.due_date


def test_totals_span_loans_without_fan_out(customer, make_loan, today, overdue_date):
    late = make_loan(customer, first_due_date=overdue_date)
    current = make_loan(customer, first_due_date=today, principal=Decimal("50000.00"))
    first, second, *_ = installments(late)

    row = dues(customer)

    assert row.outstanding == late.total_payable + current.total_payable
    assert row.overdue_amount == first.amount_due + second.amount_due
    assert row.due_today == current.emi_amount
    assert row.next_due_date == overdue_date
    assert row.active_loans == 2


def test_closed_loans_carry_no_dues(customer, make_loan, overdue_date):
    loan = make_loan(customer, first_due_date=overdue_date, tenure_months=1)
    pay(loan.installments.get(), loan.total_payable)

    row = dues(customer)

    assert (row.outstanding, row.overdue_amount, row.due_today) == (ZERO, ZERO, ZERO)
    assert row.next_due_date is None
    assert row.active_loans == 0


def test_customer_without_loans(customer):
    row = dues(customer)

    assert (row.outstanding, row.overdue_amount, row.active_loans) == (ZERO, ZERO, 0)
    assert row.next_due_date is None


def test_loan_summaries(customer, make_loan, overdue_date):
    loan = make_loan(customer, first_due_date=overdue_date)
    first, second, *_ = installments(loan)

    summary = loan_summaries().get(pk=loan.pk)

    assert summary.overdue_amount == first.amount_due + second.amount_due
    assert summary.next_due_date == first.due_date


def test_agent_route_orders_by_urgency(agent, other_agent, branch, make_loan, today, overdue_date):
    def customer_of(owner, name, **extra):
        return factories.CustomerFactory(
            branch=branch, assigned_agent=owner, full_name=name, **extra
        )

    overdue = customer_of(agent, "Zoya Overdue")
    due_today = customer_of(agent, "Yash Today")
    upcoming = customer_of(agent, "Xavier Upcoming")
    idle = customer_of(agent, "Aarav Idle")
    inactive = customer_of(agent, "Inactive", is_active=False)
    colleague = customer_of(other_agent, "Colleague")
    make_loan(overdue, first_due_date=overdue_date)
    make_loan(due_today, first_due_date=today)
    make_loan(upcoming, first_due_date=today + timedelta(days=10))
    make_loan(inactive, first_due_date=overdue_date)
    make_loan(colleague, first_due_date=overdue_date)

    assert list(agent_route(agent)) == [overdue, due_today, upcoming, idle]
