from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.collections.models import Collection
from apps.core.testing import factories
from apps.loans.selectors import get_loan, has_repayment_activity, loan_repayments

from .utils import pay

pytestmark = pytest.mark.django_db


def test_fresh_loan_balances(loan):
    loan = get_loan(loan.pk)
    first = loan.installments.get(installment_no=1)

    assert loan.outstanding == loan.total_payable
    assert loan.overdue_amount == Decimal("0.00")
    assert loan.paid_installments == 0
    assert loan.next_due_installment_no == 1
    assert loan.next_due_date == first.due_date
    assert loan.next_due_amount == first.amount_due
    assert loan.terms_locked is False


def test_overdue_counts_only_unpaid_part_of_past_due_installments(overdue_loan):
    first, second, third = overdue_loan.installments.order_by("installment_no")[:3]
    pay(second, "1000.00")

    loan = get_loan(overdue_loan.pk)

    assert third.due_date == timezone.localdate()
    assert loan.overdue_amount == first.amount_due + second.amount_due - Decimal("1000.00")
    assert loan.next_due_installment_no == 1


def test_next_due_skips_paid_installments_and_reports_balance(overdue_loan):
    first, second = overdue_loan.installments.order_by("installment_no")[:2]
    pay(first, first.amount_due)
    pay(second, "884.88")

    loan = get_loan(overdue_loan.pk)

    assert loan.paid_installments == 1
    assert loan.next_due_installment_no == 2
    assert loan.next_due_amount == second.amount_due - Decimal("884.88")
    assert loan.overdue_amount == second.amount_due - Decimal("884.88")
    assert loan.outstanding == loan.total_payable - first.amount_due - Decimal("884.88")


def test_fully_paid_loan_has_no_next_due(customer):
    loan = factories.LoanFactory(customer=customer, principal=Decimal("1000.00"), tenure_months=1)
    pay(loan.installments.get(), loan.total_payable)

    loan = get_loan(loan.pk)

    assert loan.next_due_date is None
    assert loan.next_due_amount is None
    assert loan.paid_installments == 1
    assert loan.outstanding == Decimal("0.00")


def test_repayment_activity(loan):
    assert has_repayment_activity(loan) is False

    factories.CollectionFactory(loan=loan)

    assert has_repayment_activity(loan) is True
    assert get_loan(loan.pk).terms_locked is True


def test_repayments_are_newest_first_and_include_voided(loan):
    now = timezone.now()
    older = factories.CollectionFactory(
        loan=loan,
        collected_at=now - timedelta(hours=2),
        status=Collection.Status.VOIDED,
        voided_at=now,
    )
    newer = factories.CollectionFactory(loan=loan, collected_at=now)
    factories.CollectionFactory()

    assert list(loan_repayments(loan)) == [newer, older]
