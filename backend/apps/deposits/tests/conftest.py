from decimal import Decimal

import pytest
from django.utils import timezone

from apps.collections.models import Collection
from apps.core.testing import factories


@pytest.fixture
def branch_cash(loan, manager):
    """`branch_cash("3000.00", "2000.00", short=False)` -> approved submission at the branch.

    Its cash receipts are `BRANCH_RECEIVED`; `short=True` approves it ₹500 short.
    """

    def make(*amounts: str, agent=None, short: bool = False, target_loan=None):
        target_loan = target_loan or loan
        agent = agent or target_loan.customer.assigned_agent
        amounts = [Decimal(a) for a in amounts or ("3000.00", "2000.00")]
        traits = {"short": True} if short else {"approved": True}
        reviewer = manager if target_loan.branch_id == manager.branch_id else None
        submission = factories.CashSubmissionFactory(
            agent=agent,
            expected_amount=sum(amounts),
            **traits,
            **({"reviewed_by": reviewer} if reviewer else {}),
        )
        now = timezone.now()
        for amount in amounts:
            factories.CollectionFactory(
                loan=target_loan,
                agent=agent,
                amount=amount,
                status=Collection.Status.BRANCH_RECEIVED,
                submission=submission,
                submitted_at=now,
                branch_received_at=now,
            )
        return submission

    return make


@pytest.fixture
def upi_payments(loan):
    """`upi_payments("1000.00", "500.00")` -> captured, unsettled UPI collections."""

    def make(*amounts: str, collected_at=None, target_loan=None):
        return [
            factories.CollectionFactory(
                upi=True,
                loan=target_loan or loan,
                amount=Decimal(amount),
                collected_at=collected_at or timezone.now(),
            )
            for amount in amounts
        ]

    return make


@pytest.fixture
def other_branch_loan(other_branch, other_branch_agent):
    customer = factories.CustomerFactory(branch=other_branch, assigned_agent=other_branch_agent)
    return factories.LoanFactory(customer=customer)
