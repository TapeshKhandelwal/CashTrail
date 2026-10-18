import uuid
from decimal import Decimal

import pytest

from apps.core.testing import factories
from apps.reconciliation import services


@pytest.fixture
def receive_cash(agent, loan):
    """`receive_cash("30000.00", "20000.00")` -> cash receipts held by `agent`."""

    def make(*amounts: str, loan=loan, **kwargs):
        return [
            factories.CollectionFactory(loan=loan, amount=Decimal(amount), **kwargs)
            for amount in amounts
        ]

    return make


@pytest.fixture
def submit(agent):
    """Hand receipts over through the service; `declared` defaults to their total."""

    def make(collections, *, actor=None, declared=None, denominations=None, key=None):
        submission, _ = services.create_submission(
            actor or agent,
            collection_ids=[collection.pk for collection in collections],
            declared_amount=Decimal(declared) if declared else sum(c.amount for c in collections),
            denominations=denominations,
            idempotency_key=key or uuid.uuid4(),
        )
        return submission

    return make


@pytest.fixture
def pending_submission(receive_cash, submit):
    """The brief's example: ₹50,000 of receipts awaiting the branch count."""
    return submit(receive_cash("30000.00", "20000.00"))


@pytest.fixture
def other_agent_loan(branch, other_agent):
    customer = factories.CustomerFactory(branch=branch, assigned_agent=other_agent)
    return factories.LoanFactory(customer=customer)


@pytest.fixture
def other_branch_loan(other_branch, other_branch_agent):
    customer = factories.CustomerFactory(branch=other_branch, assigned_agent=other_branch_agent)
    return factories.LoanFactory(customer=customer)
