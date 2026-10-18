import uuid

import pytest
from django.conf import settings
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts.serializers import CashTrailTokenObtainPairSerializer
from apps.core.idempotency import IDEMPOTENCY_HEADER
from apps.core.testing import factories


def pytest_configure(config):
    # Password hashing strength is irrelevant in tests and would dominate their run time.
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
    # Per process, so concurrent test runs never share throttle counters.
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


@pytest.fixture(autouse=True)
def _reset_throttles():
    """Throttle counters live in the cache; keep tests independent of each other."""
    cache.clear()


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def client_for():
    """`client_for(user)` -> APIClient authenticated with a real JWT for `user`."""

    def make(user) -> APIClient:
        client = APIClient()
        token = CashTrailTokenObtainPairSerializer.get_token(user)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
        return client

    return make


@pytest.fixture
def idempotency_headers():
    """`client.post(url, data, **idempotency_headers())` sends a fresh Idempotency-Key."""

    def make(key: uuid.UUID | str | None = None) -> dict[str, str]:
        header = f"HTTP_{IDEMPOTENCY_HEADER.upper().replace('-', '_')}"
        return {header: str(key or uuid.uuid4())}

    return make


@pytest.fixture
def branch(db):
    return factories.BranchFactory(code="BLR01", name="Bengaluru Central", city="Bengaluru")


@pytest.fixture
def other_branch(db):
    return factories.BranchFactory(code="MUM01", name="Mumbai Andheri", city="Mumbai")


@pytest.fixture
def admin_user(db):
    return factories.AdminUserFactory(username="admin")


@pytest.fixture
def finance_user(db):
    return factories.FinanceUserFactory(username="finance")


@pytest.fixture
def manager(branch):
    return factories.BranchManagerFactory(username="manager", branch=branch)


@pytest.fixture
def agent(branch):
    return factories.AgentFactory(username="agent", branch=branch)


@pytest.fixture
def other_agent(branch):
    """Another agent in the same branch as `agent`."""
    return factories.AgentFactory(username="agent2", branch=branch)


@pytest.fixture
def other_branch_manager(other_branch):
    return factories.BranchManagerFactory(username="manager_mum", branch=other_branch)


@pytest.fixture
def other_branch_agent(other_branch):
    return factories.AgentFactory(username="agent_mum", branch=other_branch)


@pytest.fixture
def customer(branch, agent):
    return factories.CustomerFactory(branch=branch, assigned_agent=agent)


@pytest.fixture
def loan(customer):
    """₹1,00,000 at 12% for 12 months (EMI ₹8,885) with its installments."""
    return factories.LoanFactory(customer=customer)


@pytest.fixture
def bank_account(db):
    return factories.BankAccountFactory()


@pytest.fixture
def gateway_bank_account(db):
    return factories.gateway_bank_account()


@pytest.fixture
def admin_client(client_for, admin_user):
    return client_for(admin_user)


@pytest.fixture
def finance_client(client_for, finance_user):
    return client_for(finance_user)


@pytest.fixture
def manager_client(client_for, manager):
    return client_for(manager)


@pytest.fixture
def agent_client(client_for, agent):
    return client_for(agent)
