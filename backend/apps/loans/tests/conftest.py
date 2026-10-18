from decimal import Decimal

import pytest

from apps.core.testing import factories

from .utils import months_ago


@pytest.fixture
def other_branch_customer(other_branch, other_branch_agent):
    return factories.CustomerFactory(branch=other_branch, assigned_agent=other_branch_agent)


@pytest.fixture
def other_branch_loan(other_branch_customer):
    return factories.LoanFactory(customer=other_branch_customer)


@pytest.fixture
def unassigned_loan(branch, other_agent):
    """Same branch as `loan`, but the customer belongs to another agent."""
    customer = factories.CustomerFactory(branch=branch, assigned_agent=other_agent)
    return factories.LoanFactory(customer=customer)


@pytest.fixture
def overdue_loan(customer):
    """Disbursed three months ago: two EMIs are past due and the third falls due today."""
    return factories.LoanFactory(customer=customer, disbursed_on=months_ago(3))


@pytest.fixture
def loan_terms():
    return {
        "principal": Decimal("100000.00"),
        "annual_interest_rate": Decimal("12.00"),
        "tenure_months": 12,
    }
