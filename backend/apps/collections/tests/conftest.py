import uuid
from decimal import Decimal

import pytest

from apps.collections.models import Collection
from apps.collections.services import record_collection
from apps.core.testing import factories


@pytest.fixture
def collect():
    """`collect(agent, loan, "5000.00")` records a cash repayment and returns the receipt."""

    def make(agent, loan, amount, **kwargs) -> Collection:
        kwargs.setdefault("mode", Collection.Mode.CASH)
        kwargs.setdefault("idempotency_key", uuid.uuid4())
        kwargs.setdefault("confirm_duplicate", True)
        collection, _ = record_collection(actor=agent, loan=loan, amount=Decimal(amount), **kwargs)
        return collection

    return make


@pytest.fixture
def other_branch_loan(other_branch, other_branch_agent):
    customer = factories.CustomerFactory(branch=other_branch, assigned_agent=other_branch_agent)
    return factories.LoanFactory(customer=customer)


@pytest.fixture
def other_agent_loan(branch, other_agent):
    """A loan in the same branch whose customer is assigned to `other_agent`."""
    customer = factories.CustomerFactory(branch=branch, assigned_agent=other_agent)
    return factories.LoanFactory(customer=customer)
