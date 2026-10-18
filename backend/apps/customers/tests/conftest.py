from datetime import timedelta

import pytest
from dateutil.relativedelta import relativedelta

from apps.core.dates import business_date
from apps.core.testing import factories
from apps.loans.models import Loan


@pytest.fixture
def today():
    return business_date()


@pytest.fixture
def make_loan():
    """`make_loan(customer, first_due_date=...)`: monthly schedule starting on that date."""

    def make(customer, *, first_due_date, **overrides) -> Loan:
        return factories.LoanFactory(
            customer=customer,
            first_due_date=first_due_date,
            disbursed_on=first_due_date - relativedelta(months=1),
            **overrides,
        )

    return make


@pytest.fixture
def overdue_date(today):
    """First due date that leaves two installments overdue and none due today."""
    return today - timedelta(days=45)


@pytest.fixture
def customers(customer, other_agent, other_branch_agent):
    """`own`: assigned to `agent`; `colleague`: same branch, other agent; `foreign`: MUM01."""
    return {
        "own": customer,
        "colleague": factories.CustomerFactory(branch=customer.branch, assigned_agent=other_agent),
        "foreign": factories.CustomerFactory(
            branch=other_branch_agent.branch, assigned_agent=other_branch_agent
        ),
    }


@pytest.fixture
def clients(client_for, admin_user, finance_user, manager, agent):
    return {
        "admin": client_for(admin_user),
        "finance": client_for(finance_user),
        "manager": client_for(manager),
        "agent": client_for(agent),
    }
