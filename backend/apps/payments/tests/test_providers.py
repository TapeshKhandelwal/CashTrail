import json
from decimal import Decimal

import pytest
import requests
from razorpay.errors import BadRequestError

from apps.payments.exceptions import GatewayError
from apps.payments.models import GatewayProvider
from apps.payments.providers import MockProvider, PaymentOutcome, RazorpayProvider, get_provider
from apps.payments.providers.base import hmac_sha256

from .helpers import RAZORPAY_KEY_SECRET, RAZORPAY_WEBHOOK_SECRET

ORDER_ID = "order_RzpTest000001"
PAYMENT_ID = "pay_RzpTest000001"


@pytest.fixture
def provider() -> RazorpayProvider:
    return RazorpayProvider(
        key_id="rzp_test_cashtrail",
        key_secret=RAZORPAY_KEY_SECRET,
        webhook_secret=RAZORPAY_WEBHOOK_SECRET,
    )


class FakeOrders:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.calls = response, error, []

    def create(self, data, **options):
        self.calls.append((data, options))
        if self.error:
            raise self.error
        return self.response


class FakeClient:
    def __init__(self, orders):
        self.order = orders


class FakeOrderPayments:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.calls = response, error, []

    def payments(self, order_id, **options):
        self.calls.append((order_id, options))
        if self.error:
            raise self.error
        return self.response


class TestCheckoutSignature:
    def test_valid_signature_is_accepted(self, provider):
        signature = hmac_sha256(RAZORPAY_KEY_SECRET, f"{ORDER_ID}|{PAYMENT_ID}")

        assert provider.verify_checkout(ORDER_ID, PAYMENT_ID, signature)

    @pytest.mark.parametrize(
        "signature",
        [
            "",
            "0" * 64,
            hmac_sha256("another_secret", f"{ORDER_ID}|{PAYMENT_ID}"),
            hmac_sha256(RAZORPAY_KEY_SECRET, f"order_Other0000001|{PAYMENT_ID}"),
        ],
        ids=["empty", "garbage", "wrong-secret", "other-order"],
    )
    def test_invalid_signature_is_rejected(self, provider, signature):
        assert not provider.verify_checkout(ORDER_ID, PAYMENT_ID, signature)


class TestWebhookSignature:
    body = b'{"event":"payment.captured","payload":{}}'

    def test_signature_over_raw_body_is_accepted(self, provider):
        assert provider.verify_webhook(self.body, hmac_sha256(RAZORPAY_WEBHOOK_SECRET, self.body))

    def test_signature_of_reserialized_json_is_rejected(self, provider):
        reserialized = json.dumps(json.loads(self.body)).encode()

        assert reserialized != self.body
        assert not provider.verify_webhook(
            self.body, hmac_sha256(RAZORPAY_WEBHOOK_SECRET, reserialized)
        )

    def test_checkout_secret_does_not_sign_webhooks(self, provider):
        assert not provider.verify_webhook(self.body, hmac_sha256(RAZORPAY_KEY_SECRET, self.body))

    def test_missing_signature_is_rejected(self, provider):
        assert not provider.verify_webhook(self.body, "")

    def test_non_ascii_signature_is_rejected_not_crashed(self, provider):
        assert not provider.verify_webhook(self.body, "\xe9" * 64)
        assert not provider.verify_checkout(ORDER_ID, PAYMENT_ID, "\xe9" * 64)

    def test_unconfigured_secret_rejects_everything(self):
        unconfigured = RazorpayProvider(key_id="", key_secret="", webhook_secret="")

        assert not unconfigured.verify_webhook(self.body, hmac_sha256("", self.body))


class TestCreateOrder:
    def test_sends_paise_and_returns_the_order(self, provider):
        orders = FakeOrders(response={"id": ORDER_ID, "amount": 500050, "currency": "INR"})
        provider.client = FakeClient(orders)

        result = provider.create_order(Decimal("5000.50"), "ORD-BLR01-20261017-00001", {"a": "b"})

        assert result.order_id == ORDER_ID
        assert result.amount_paise == 500050
        (data, options), *_ = orders.calls
        assert data == {
            "amount": 500050,
            "currency": "INR",
            "receipt": "ORD-BLR01-20261017-00001",
            "notes": {"a": "b"},
        }
        assert options["timeout"] == (3, 10)

    @pytest.mark.parametrize(
        "error",
        [BadRequestError("bad amount"), requests.Timeout("slow"), requests.ConnectionError()],
    )
    def test_gateway_failures_become_gateway_error(self, provider, error):
        provider.client = FakeClient(FakeOrders(error=error))

        with pytest.raises(GatewayError) as excinfo:
            provider.create_order(Decimal("100.00"), "ORD-1", {})
        assert excinfo.value.status_code == 502
        assert excinfo.value.code == "GATEWAY_ERROR"

    def test_malformed_response_becomes_gateway_error(self, provider):
        provider.client = FakeClient(FakeOrders(response={"error": "?"}))

        with pytest.raises(GatewayError):
            provider.create_order(Decimal("100.00"), "ORD-1", {})


class TestParseWebhook:
    def test_payment_captured(self, provider):
        payload = {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": PAYMENT_ID,
                        "order_id": ORDER_ID,
                        "amount": 500050,
                        "created_at": 1792224000,
                    }
                }
            },
        }

        event = provider.parse_webhook(payload, event_id="evt_1")

        assert event.event_id == "evt_1"
        assert event.event_type == "payment.captured"
        assert event.order_id == ORDER_ID
        assert event.payment_id == PAYMENT_ID
        assert event.amount == Decimal("5000.50")
        assert event.occurred_at.timestamp() == 1792224000
        assert event.outcome == PaymentOutcome.CAPTURED

    def test_events_reconciliation_ignores_have_no_outcome(self, provider):
        assert provider.parse_webhook({"event": "refund.created"}).outcome is None

    def test_payment_failed_carries_the_reason(self, provider):
        payload = {
            "event": "payment.failed",
            "payload": {
                "payment": {
                    "entity": {
                        "id": PAYMENT_ID,
                        "order_id": ORDER_ID,
                        "error_description": "Payment was declined by the bank.",
                    }
                }
            },
        }

        event = provider.parse_webhook(payload)

        assert event.failure_reason == "Payment was declined by the bank."
        assert event.event_id == f"payment.failed:{PAYMENT_ID}"

    def test_unexpected_shapes_do_not_crash(self, provider):
        event = provider.parse_webhook({"event": "refund.created", "payload": None})

        assert (event.order_id, event.payment_id, event.amount) == ("", "", None)


class TestFetchPayments:
    def test_maps_razorpay_statuses_onto_outcomes(self, provider):
        items = [
            {"id": "pay_1", "status": "captured", "amount": 500050, "created_at": 1792224000},
            {"id": "pay_2", "status": "failed", "error_description": "Declined"},
            {"id": "pay_3", "status": "authorized"},
            {"id": "pay_4", "status": "refunded"},
        ]
        orders = FakeOrderPayments(response={"entity": "collection", "items": items})
        provider.client = FakeClient(orders)

        payments = provider.fetch_payments(ORDER_ID)

        assert [p.outcome for p in payments] == [
            PaymentOutcome.CAPTURED,
            PaymentOutcome.FAILED,
            PaymentOutcome.PENDING,
            PaymentOutcome.CAPTURED,
        ]
        assert payments[0].amount == Decimal("5000.50")
        assert payments[0].occurred_at.timestamp() == 1792224000
        assert payments[1].failure_reason == "Declined"
        assert orders.calls == [(ORDER_ID, {"timeout": (3, 10)})]

    @pytest.mark.parametrize(
        ("response", "error"),
        [(None, requests.ReadTimeout()), ({"error": "?"}, None)],
        ids=["timeout", "malformed"],
    )
    def test_lookup_failures_become_gateway_error(self, provider, response, error):
        provider.client = FakeClient(FakeOrderPayments(response=response, error=error))

        with pytest.raises(GatewayError):
            provider.fetch_payments(ORDER_ID)

    def test_mock_has_nothing_to_look_up(self):
        assert MockProvider(secret="s").fetch_payments(ORDER_ID) == []


class TestMockProvider:
    def test_ids_are_deterministic(self):
        gateway = MockProvider(secret="s")
        first = gateway.create_order(Decimal("100.00"), "ORD-1", {})
        again = gateway.create_order(Decimal("100.00"), "ORD-1", {})
        other = gateway.create_order(Decimal("100.00"), "ORD-2", {})

        assert first.order_id == again.order_id != other.order_id
        assert first.order_id.startswith("order_")
        assert first.amount_paise == 10000
        assert gateway.payment_id_for(first.order_id, outcome="success").startswith("pay_")

    def test_its_signatures_pass_the_shared_verification(self):
        gateway = MockProvider(secret="s")
        payment_id = gateway.payment_id_for(ORDER_ID, outcome="success")
        body = b'{"event":"order.paid"}'

        assert gateway.verify_checkout(
            ORDER_ID, payment_id, gateway.sign_checkout(ORDER_ID, payment_id)
        )
        assert not gateway.verify_checkout(
            ORDER_ID, payment_id, MockProvider(secret="other").sign_checkout(ORDER_ID, payment_id)
        )
        assert gateway.verify_webhook(body, gateway.sign_webhook(body))


class TestGetProvider:
    def test_mock_by_default(self):
        provider = get_provider()

        assert isinstance(provider, MockProvider)
        assert provider.code == GatewayProvider.MOCK
        assert provider.key_id == ""

    def test_razorpay_when_configured(self, razorpay_gateway):
        assert type(razorpay_gateway) is RazorpayProvider
        assert razorpay_gateway.key_id == "rzp_test_cashtrail"
        assert razorpay_gateway.environment == "test"
        assert razorpay_gateway.checkout_script.startswith("https://checkout.razorpay.com/")

    def test_live_razorpay_keys_run_live(self):
        provider = RazorpayProvider(key_id="rzp_live_x", key_secret="s", webhook_secret="w")

        assert provider.environment == "live"
