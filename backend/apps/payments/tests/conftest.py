import uuid
from decimal import Decimal

import pytest

from apps.core.testing import factories
from apps.payments import services
from apps.payments.models import GatewayOrder, GatewayProvider
from apps.payments.providers import CashfreeProvider, MockProvider, get_provider

from .helpers import (
    CASHFREE_APP_ID,
    CASHFREE_SECRET_KEY,
    RAZORPAY_KEY_SECRET,
    RAZORPAY_WEBHOOK_SECRET,
    FakeCashfree,
)


@pytest.fixture(autouse=True)
def _mock_gateway(settings):
    """Tests run against the mock gateway unless they opt into `razorpay_gateway`."""
    settings.PAYMENT_PROVIDER = "mock"


@pytest.fixture
def razorpay_gateway(settings):
    settings.PAYMENT_PROVIDER = "razorpay"
    settings.RAZORPAY_KEY_ID = "rzp_test_cashtrail"
    settings.RAZORPAY_KEY_SECRET = RAZORPAY_KEY_SECRET
    settings.RAZORPAY_WEBHOOK_SECRET = RAZORPAY_WEBHOOK_SECRET
    return get_provider()


@pytest.fixture
def cashfree_api(monkeypatch) -> FakeCashfree:
    """Every Cashfree provider talks to this fake instead of the network."""
    api = FakeCashfree()
    monkeypatch.setattr(CashfreeProvider, "session", property(lambda self: api))
    return api


@pytest.fixture
def cashfree_gateway(settings, cashfree_api) -> CashfreeProvider:
    settings.PAYMENT_PROVIDER = "cashfree"
    settings.CASHFREE_APP_ID = CASHFREE_APP_ID
    settings.CASHFREE_SECRET_KEY = CASHFREE_SECRET_KEY
    settings.CASHFREE_ENVIRONMENT = "sandbox"
    settings.CASHFREE_NOTIFY_URL = ""
    settings.CASHFREE_RETURN_URL = ""
    return get_provider()


@pytest.fixture
def cashfree_order(cashfree_gateway, raise_order, agent, loan) -> GatewayOrder:
    """A ₹5,000 order raised through the Cashfree gateway instead of the mock."""
    return raise_order(agent, loan)


@pytest.fixture
def mock_gateway() -> MockProvider:
    return get_provider()


@pytest.fixture
def raise_order():
    """`raise_order(agent, loan, "5000.00")` creates a UPI order through the service."""

    def make(agent, loan, amount="5000.00", **kwargs) -> GatewayOrder:
        kwargs.setdefault("idempotency_key", uuid.uuid4())
        order, _ = services.create_order(agent, loan=loan, amount=Decimal(amount), **kwargs)
        return order

    return make


@pytest.fixture
def order(raise_order, agent, loan) -> GatewayOrder:
    return raise_order(agent, loan)


@pytest.fixture
def razorpay_order(agent, loan) -> GatewayOrder:
    return factories.GatewayOrderFactory(
        provider=GatewayProvider.RAZORPAY,
        provider_order_id="order_RzpTest000001",
        loan=loan,
        agent=agent,
        amount=Decimal("5000.00"),
    )


@pytest.fixture
def checkout(mock_gateway):
    """`checkout(order)` -> (payment_id, signature) as the mock gateway's checkout returns them."""

    def make(order, outcome="success") -> tuple[str, str]:
        payment_id = mock_gateway.payment_id_for(order.provider_order_id, outcome=outcome)
        return payment_id, mock_gateway.sign_checkout(order.provider_order_id, payment_id)

    return make
