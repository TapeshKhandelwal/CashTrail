"""A small book of business covering every lifecycle state, with hand-computed KPIs.

Branch BLR01: `agent` (loan L1, due today) and `other_agent` (loan L2, two overdue
installments). Branch MUM01: `other_branch_agent` (loan L3 due today, plus a closed
loan L4). Times are relative to `anchor`, today 12:00 IST, and the dashboard period
is the last seven days.
"""

from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from dateutil.relativedelta import relativedelta
from django.utils import timezone

from apps.collections.models import Collection
from apps.core.dates import business_date, day_bounds
from apps.core.testing import factories
from apps.dashboard.selectors import DashboardFilters
from apps.deposits.models import BankDeposit
from apps.loans.models import Installment, Loan
from apps.reconciliation.models import CashSubmission, Discrepancy


@pytest.fixture
def today():
    return business_date()


@pytest.fixture
def anchor(today):
    return day_bounds(today)[0] + timedelta(hours=12)


@pytest.fixture
def period(today):
    return {"date_from": (today - timedelta(days=7)).isoformat(), "date_to": today.isoformat()}


@pytest.fixture
def make_filters(today):
    def make(**overrides) -> DashboardFilters:
        return DashboardFilters(
            **{"date_from": today - timedelta(days=7), "date_to": today, **overrides}
        )

    return make


@pytest.fixture
def scenario(
    today,
    anchor,
    branch,
    other_branch,
    manager,
    agent,
    other_agent,
    other_branch_agent,
    bank_account,
    gateway_bank_account,
):
    def hours(n):
        return anchor - timedelta(hours=n)

    def days(n):
        return anchor - timedelta(days=n)

    l1 = factories.LoanFactory(
        customer=factories.CustomerFactory(branch=branch, assigned_agent=agent)
    )
    l2 = factories.LoanFactory(
        customer=factories.CustomerFactory(branch=branch, assigned_agent=other_agent),
        disbursed_on=today - timedelta(days=70),
        first_due_date=today - timedelta(days=40),
    )
    l3 = factories.LoanFactory(
        customer=factories.CustomerFactory(branch=other_branch, assigned_agent=other_branch_agent)
    )
    l4 = factories.LoanFactory(
        customer=l3.customer,
        disbursed_on=today - relativedelta(months=1) + timedelta(days=5),
        first_due_date=today + timedelta(days=5),
    )
    Loan.objects.filter(pk=l1.pk).update(amount_paid=Decimal("12000.00"))
    Loan.objects.filter(pk=l2.pk).update(amount_paid=Decimal("4000.00"))
    Loan.objects.filter(pk=l4.pk).update(
        amount_paid=l4.total_payable, status=Loan.Status.CLOSED, closed_at=timezone.now()
    )
    Installment.objects.filter(loan=l2, installment_no=1).update(
        amount_paid=Decimal("4000.00"), status=Installment.Status.PARTIALLY_PAID
    )

    d_settled = factories.BankDepositFactory(
        branch=branch,
        created_by=manager,
        bank_account=bank_account,
        settled=True,
        expected_amount=Decimal("4000.00"),
        deposit_date=today - timedelta(days=3),
        settled_on=today - timedelta(days=1),
    )
    d_pending = factories.BankDepositFactory(
        branch=branch,
        created_by=manager,
        bank_account=bank_account,
        expected_amount=Decimal("2500.00"),
        deposit_date=today - timedelta(days=5),
    )
    d_failed = factories.BankDepositFactory(
        branch=branch,
        created_by=manager,
        bank_account=bank_account,
        failed=True,
        expected_amount=Decimal("900.00"),
        deposit_date=today - timedelta(days=2),
    )
    d_gateway = factories.BankDepositFactory(
        gateway=True,
        status=BankDeposit.Status.SETTLED_WITH_MISMATCH,
        expected_amount=Decimal("1200.00"),
        fee_amount=Decimal("20.00"),
        tax_amount=Decimal("3.60"),
        deposited_amount=Decimal("1176.40"),
        settled_amount=Decimal("1170.00"),
        deposit_date=today - timedelta(days=1),
        settled_on=today,
        settled_at=anchor,
        settlement_reference="STMT-GW-1",
    )

    s_pending = factories.CashSubmissionFactory(agent=agent, expected_amount=Decimal("2000.00"))
    s_short = factories.CashSubmissionFactory(
        agent=agent, short=True, expected_amount=Decimal("3000.00"), reviewed_by=manager
    )
    s_ok = factories.CashSubmissionFactory(
        agent=agent,
        approved=True,
        expected_amount=Decimal("4000.00"),
        reviewed_by=manager,
        deposit=d_settled,
    )
    s_other = factories.CashSubmissionFactory(
        agent=other_agent,
        approved=True,
        expected_amount=Decimal("2500.00"),
        reviewed_by=manager,
        deposit=d_pending,
    )
    s_rejected = factories.CashSubmissionFactory(
        agent=agent, rejected=True, expected_amount=Decimal("600.00"), reviewed_by=manager
    )

    def collect(loan, amount, at, **kwargs):
        return factories.CollectionFactory(
            loan=loan, amount=Decimal(amount), collected_at=at, **kwargs
        )

    receipts = {
        "c1": collect(l1, "1000.00", hours(2)),
        "c2": collect(l1, "500.00", hours(36)),
        "c3": collect(
            l1,
            "2000.00",
            days(3),
            status=Collection.Status.SUBMITTED,
            submission=s_pending,
            submitted_at=days(2),
        ),
        "c4": collect(
            l1,
            "3000.00",
            days(4),
            status=Collection.Status.BRANCH_RECEIVED,
            submission=s_short,
            branch_received_at=days(3),
        ),
        "c5": collect(
            l1,
            "4000.00",
            days(5),
            status=Collection.Status.SETTLED,
            submission=s_ok,
            deposit=d_settled,
            settled_at=days(1),
        ),
        "c6": collect(
            l1,
            "700.00",
            hours(1),
            status=Collection.Status.VOIDED,
            voided_at=hours(1),
            void_reason="Wrong customer.",
            voided_by=agent,
        ),
        "c7": collect(l1, "1500.00", days(1), upi=True, agent=agent),
        "c8": collect(
            l2,
            "2500.00",
            days(6),
            status=Collection.Status.DEPOSITED,
            submission=s_other,
            deposit=d_pending,
            deposited_at=days(5),
        ),
        "c9": collect(l3, "800.00", hours(2)),
        "c10": collect(
            l3,
            "1200.00",
            days(2),
            upi=True,
            status=Collection.Status.SETTLED,
            deposit=d_gateway,
            settled_at=anchor,
        ),
        "c11": collect(l1, "999.00", days(20)),
    }

    shortage = factories.DiscrepancyFactory(
        submission=s_short, amount=Decimal("500.00"), raised_by=manager
    )
    gateway_mismatch = factories.DiscrepancyFactory(
        kind=Discrepancy.Kind.GATEWAY_MISMATCH,
        direction=Discrepancy.Direction.SHORT,
        amount=Decimal("6.40"),
        submission=None,
        deposit=d_gateway,
        branch=None,
        agent=None,
        reason_code=Discrepancy.ReasonCode.BANK_CHARGES,
        raised_by=None,
    )
    resolved = factories.DiscrepancyFactory(
        kind=Discrepancy.Kind.DEPOSIT_MISMATCH,
        direction=Discrepancy.Direction.SHORT,
        amount=Decimal("100.00"),
        submission=None,
        deposit=d_pending,
        branch=branch,
        agent=None,
        status=Discrepancy.Status.RESOLVED,
        resolved_at=timezone.now(),
        resolution_notes="Bank corrected the slip.",
        raised_by=manager,
    )

    assert CashSubmission.objects.filter(status=CashSubmission.Status.SUBMITTED).count() == 1
    return SimpleNamespace(
        loans={"l1": l1, "l2": l2, "l3": l3, "l4": l4},
        deposits={
            "settled": d_settled,
            "pending": d_pending,
            "failed": d_failed,
            "gateway": d_gateway,
        },
        submissions={
            "pending": s_pending,
            "short": s_short,
            "ok": s_ok,
            "other": s_other,
            "rejected": s_rejected,
        },
        receipts=receipts,
        discrepancies={
            "shortage": shortage,
            "gateway": gateway_mismatch,
            "resolved": resolved,
        },
    )
