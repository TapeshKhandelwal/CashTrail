"""Cashfree: the provider against its HTTP API, status checks and webhooks end to end."""

import json
import re
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
import requests
from django.core.management import call_command
from django.utils import timezone

from apps.audit.models import AuditAction, AuditLog
from apps.collections.models import Collection
from apps.core.testing import factories
from apps.payments import services
from apps.payments.exceptions import GatewayError, PaymentAmountMismatch
from apps.payments.models import GatewayOrder, GatewayProvider, WebhookEvent
from apps.payments.providers import (
    CashfreeProvider,
    CheckoutCustomer,
    PaymentOutcome,
    get_provider,
)
from apps.payments.providers.cashfree import API_VERSION, USER_DROPPED_REASON

from .helpers import (
    CASHFREE_APP_ID,
    CASHFREE_SECRET_KEY,
    CASHFREE_SESSION_PREFIX,
    FakeResponse,
    cashfree_payment,
    cashfree_sign,
    cashfree_webhook_body,
)

ORDERS_URL = "/api/payments/orders/"
VERIFY_URL = "/api/payments/verify/"
CONFIG_URL = "/api/payments/config/"
WEBHOOK_URL = "/api/payments/webhooks/cashfree/"
TIMESTAMP = "1792224000123"

CUSTOMER = CheckoutCustomer(
    customer_id="CUS-BLR01-00007", name="Asha Kulkarni", phone="+91 98765 43210"
)


def refresh_url(order) -> str:
    return f"{ORDERS_URL}{order.pk}/refresh/"


def error_code(response) -> str:
    return response.json()["error"]["code"]


@pytest.fixture
def provider(cashfree_api) -> CashfreeProvider:
    return CashfreeProvider(app_id=CASHFREE_APP_ID, secret_key=CASHFREE_SECRET_KEY)


# ---------------------------------------------------------------------------- the provider


class TestCreateOrder:
    def test_sends_the_order_and_returns_the_payment_session(self, provider, cashfree_api):
        before = timezone.now()

        order = provider.create_order(
            Decimal("5000.50"),
            "ORD-BLR01-20261018-000001",
            {"loan_number": "LN-1"},
            customer=CUSTOMER,
        )

        assert re.fullmatch(r"ORD-BLR01-20261018-000001-[0-9a-f]{6}", order.order_id)
        assert order.amount_paise == 500050
        assert order.checkout_token == f"{CASHFREE_SESSION_PREFIX}{order.order_id}"
        (sent,) = cashfree_api.requests
        assert (sent.method, sent.url) == ("POST", "https://sandbox.cashfree.com/pg/orders")
        assert sent.headers == {"x-request-id": "ORD-BLR01-20261018-000001"}
        assert sent.timeout == (3, 10)
        body = sent.json
        assert body["order_id"] == order.order_id
        assert body["order_amount"] == 5000.5
        assert body["order_currency"] == "INR"
        assert body["customer_details"] == {
            "customer_id": "CUS-BLR01-00007",
            "customer_phone": "9876543210",
            "customer_name": "Asha Kulkarni",
        }
        assert body["order_meta"] == {"payment_methods": "upi"}
        assert body["order_tags"] == {"loan_number": "LN-1"}
        # Cashfree refuses expiries less than 15 minutes out.
        expires = datetime.fromisoformat(body["order_expiry_time"])
        assert expires - before > timedelta(minutes=15)

    def test_authenticates_with_the_app_id_secret_and_api_version(self):
        provider = CashfreeProvider(app_id=CASHFREE_APP_ID, secret_key=CASHFREE_SECRET_KEY)

        assert provider.session.headers["x-client-id"] == CASHFREE_APP_ID
        assert provider.session.headers["x-client-secret"] == CASHFREE_SECRET_KEY
        assert provider.session.headers["x-api-version"] == API_VERSION

    def test_production_uses_the_live_api(self, cashfree_api):
        provider = CashfreeProvider(app_id="a", secret_key="s", environment="production")

        provider.create_order(Decimal("1.00"), "ORD-1", {}, customer=CUSTOMER)

        assert cashfree_api.requests[0].url == "https://api.cashfree.com/pg/orders"

    def test_unknown_environment_is_refused(self):
        with pytest.raises(ValueError):
            CashfreeProvider(app_id="a", secret_key="s", environment="staging")

    def test_notify_and_return_urls_are_sent_when_configured(self, cashfree_api):
        provider = CashfreeProvider(
            app_id="a",
            secret_key="s",
            notify_url="https://api.example.com/api/payments/webhooks/cashfree/",
            return_url="https://app.example.com/app/agent/collect/upi-return?order_id={order_id}",
        )

        order = provider.create_order(Decimal("1.00"), "ORD-BLR01-1", {}, customer=CUSTOMER)

        assert cashfree_api.requests[0].json["order_meta"] == {
            "payment_methods": "upi",
            "notify_url": "https://api.example.com/api/payments/webhooks/cashfree/",
            "return_url": "https://app.example.com/app/agent/collect/upi-return?order_id="
            + order.order_id,
        }

    def test_order_ids_differ_between_deployments_sharing_one_account(self, provider):
        # Two databases issue the same receipt; Cashfree needs distinct order ids.
        first = provider.create_order(Decimal("1.00"), "ORD-BLR01-1", {}, customer=CUSTOMER)
        second = provider.create_order(Decimal("1.00"), "ORD-BLR01-1", {}, customer=CUSTOMER)

        assert first.order_id != second.order_id
        assert first.order_id.startswith("ORD-BLR01-1-")
        assert len(first.order_id) <= 45

    def test_customer_details_are_cleaned_for_cashfree(self, provider, cashfree_api):
        customer = CheckoutCustomer(
            customer_id="CUS/01 7", name="Al", phone="98765-43210", email="al@example.com"
        )

        provider.create_order(Decimal("1.00"), "ORD-1", {"empty": ""}, customer=customer)

        body = cashfree_api.requests[0].json
        # A name under 3 characters is optional, so it is left out rather than refused.
        assert body["customer_details"] == {
            "customer_id": "CUS_01_7",
            "customer_phone": "9876543210",
            "customer_email": "al@example.com",
        }
        assert body["order_tags"] == {}

    @pytest.mark.parametrize(
        "error",
        [
            requests.ConnectTimeout(),
            requests.ConnectionError(),
            FakeResponse(401, {"message": "authentication Failed", "code": "request_failed"}),
            FakeResponse(409, {"code": "order_already_exists", "message": "order with same id"}),
            FakeResponse(500, "<html>Bad gateway</html>"),
        ],
        ids=["timeout", "unreachable", "bad-keys", "duplicate-id", "server-error"],
    )
    def test_gateway_failures_become_gateway_error(self, provider, cashfree_api, error):
        cashfree_api.error = error

        with pytest.raises(GatewayError) as excinfo:
            provider.create_order(Decimal("100.00"), "ORD-1", {}, customer=CUSTOMER)

        assert excinfo.value.status_code == 502
        assert excinfo.value.details["provider"] == GatewayProvider.CASHFREE

    def test_cashfree_error_code_is_kept(self, provider, cashfree_api):
        cashfree_api.error = FakeResponse(409, {"code": "order_already_exists"})

        with pytest.raises(GatewayError) as excinfo:
            provider.create_order(Decimal("100.00"), "ORD-1", {}, customer=CUSTOMER)

        assert excinfo.value.details["gateway_code"] == "order_already_exists"

    @pytest.mark.parametrize(
        "response",
        [
            {"order_id": "ORD-1", "order_amount": 99.99, "order_currency": "INR",
             "payment_session_id": "session_x"},
            {"order_id": "ORD-1", "order_amount": 100.0, "order_currency": "INR",
             "payment_session_id": ""},
            {"order_id": "ORD-1"},
        ],
        ids=["other-amount", "no-session", "truncated"],
    )  # fmt: skip
    def test_unusable_order_becomes_gateway_error(self, provider, cashfree_api, response):
        cashfree_api.error = FakeResponse(200, response)

        with pytest.raises(GatewayError):
            provider.create_order(Decimal("100.00"), "ORD-1", {}, customer=CUSTOMER)


class TestCheckoutSignature:
    def test_cashfree_checkout_has_no_signature_to_trust(self, provider):
        assert not provider.verify_checkout("ORD-1", "5114910000001", "anything")


class TestWebhookSignature:
    body = b'{"data":{"order":{"order_amount":170.00}},"type":"PAYMENT_SUCCESS_WEBHOOK"}'

    def test_signature_over_timestamp_and_raw_body_is_accepted(self, provider):
        signature = cashfree_sign(self.body, TIMESTAMP)

        assert provider.verify_webhook(self.body, signature, timestamp=TIMESTAMP)

    def test_signature_of_reserialized_json_is_rejected(self, provider):
        # Parsing turns 170.00 into 170.0; Cashfree signed the bytes it sent.
        reserialized = json.dumps(json.loads(self.body)).encode()

        assert reserialized != self.body
        assert not provider.verify_webhook(
            self.body, cashfree_sign(reserialized, TIMESTAMP), timestamp=TIMESTAMP
        )

    def test_signature_for_another_timestamp_is_rejected(self, provider):
        signature = cashfree_sign(self.body, TIMESTAMP)

        assert not provider.verify_webhook(self.body, signature, timestamp="1792224000999")

    def test_other_secret_is_rejected(self, provider):
        signature = cashfree_sign(self.body, TIMESTAMP, secret="cfsk_ma_test_someone_else")

        assert not provider.verify_webhook(self.body, signature, timestamp=TIMESTAMP)

    @pytest.mark.parametrize("missing", ["signature", "timestamp"])
    def test_missing_header_is_rejected(self, provider, missing):
        signature = cashfree_sign(self.body, TIMESTAMP)
        kwargs = {"signature": signature, "timestamp": TIMESTAMP, missing: ""}

        assert not provider.verify_webhook(self.body, **kwargs)

    @pytest.mark.parametrize(
        ("signature", "timestamp"), [("\xe9t\xe9", TIMESTAMP), ("c2ln", "\xe9")]
    )
    def test_non_ascii_headers_are_rejected_not_crashed(self, provider, signature, timestamp):
        assert not provider.verify_webhook(self.body, signature, timestamp=timestamp)

    def test_unconfigured_secret_rejects_everything(self):
        unconfigured = CashfreeProvider(app_id="", secret_key="")

        assert not unconfigured.verify_webhook(
            self.body, cashfree_sign(self.body, TIMESTAMP, secret=""), timestamp=TIMESTAMP
        )


class TestParseWebhook:
    def parse(self, provider, raw: bytes, **kwargs):
        return provider.parse_webhook(json.loads(raw), **kwargs)

    def test_payment_success(self, provider):
        order = factories.GatewayOrderFactory.build(
            provider_order_id="ORD-BLR01-1", amount=Decimal("1250.10")
        )

        event = self.parse(
            provider, cashfree_webhook_body("PAYMENT_SUCCESS_WEBHOOK", order, "5114910000001")
        )

        assert event.outcome == PaymentOutcome.CAPTURED
        assert event.event_type == "PAYMENT_SUCCESS_WEBHOOK"
        assert event.event_id == "PAYMENT_SUCCESS_WEBHOOK:5114910000001"
        assert (event.order_id, event.payment_id) == ("ORD-BLR01-1", "5114910000001")
        assert event.amount == Decimal("1250.10")
        assert event.occurred_at == datetime.fromisoformat("2026-10-18T10:15:06+05:30")

    def test_surcharge_paid_on_top_is_not_counted_towards_the_order(self, provider):
        order = factories.GatewayOrderFactory.build(amount=Decimal("1000.00"))
        payload = cashfree_payment(order, surcharge=Decimal("23.60"))

        (payment,) = provider_payments(provider, payload)

        assert payment.amount == Decimal("1000.00")

    def test_payment_failed_carries_the_bank_reason(self, provider):
        order = factories.GatewayOrderFactory.build(provider_order_id="ORD-BLR01-1")
        raw = cashfree_webhook_body(
            "PAYMENT_FAILED_WEBHOOK", order, error="Issue originating from user."
        )

        event = self.parse(provider, raw)

        assert event.outcome == PaymentOutcome.FAILED
        assert event.failure_reason == "Issue originating from user."

    def test_user_dropped_is_a_failed_attempt(self, provider):
        order = factories.GatewayOrderFactory.build(provider_order_id="ORD-BLR01-1")

        event = self.parse(provider, cashfree_webhook_body("PAYMENT_USER_DROPPED_WEBHOOK", order))

        assert event.outcome == PaymentOutcome.FAILED
        assert event.failure_reason == USER_DROPPED_REASON

    def test_unreadable_amount_and_time_are_left_empty(self, provider):
        payload = {
            "type": "PAYMENT_SUCCESS_WEBHOOK",
            "data": {"payment": {"payment_amount": "n/a", "payment_time": "yesterday"}},
        }

        event = provider.parse_webhook(payload)

        assert (event.amount, event.occurred_at) == (None, None)

    def test_events_reconciliation_ignores_have_no_outcome(self, provider):
        event = provider.parse_webhook({"type": "REFUND_STATUS_WEBHOOK", "data": {}})

        assert event.outcome is None

    @pytest.mark.parametrize(
        "payload",
        [{}, {"data": None}, {"data": {"order": [], "payment": "x"}}, {"type": 5, "data": []}],
    )
    def test_unexpected_shapes_do_not_crash(self, provider, payload):
        event = provider.parse_webhook(payload)

        assert (event.order_id, event.payment_id, event.amount, event.occurred_at) == (
            "",
            "",
            None,
            None,
        )


def provider_payments(provider, *payments):
    order_id = "ORD-1"
    provider.session.payments[order_id] = list(payments)
    return provider.fetch_payments(order_id)


class TestFetchPayments:
    @pytest.mark.parametrize(
        ("status", "outcome"),
        [
            ("SUCCESS", PaymentOutcome.CAPTURED),
            ("FAILED", PaymentOutcome.FAILED),
            ("USER_DROPPED", PaymentOutcome.FAILED),
            ("CANCELLED", PaymentOutcome.FAILED),
            ("VOID", PaymentOutcome.FAILED),
            ("PENDING", PaymentOutcome.PENDING),
            ("NOT_ATTEMPTED", PaymentOutcome.PENDING),
            ("SOMETHING_NEW", PaymentOutcome.PENDING),
        ],
    )
    def test_statuses_map_onto_outcomes(self, provider, status, outcome):
        order = factories.GatewayOrderFactory.build(provider_order_id="ORD-1")

        (payment,) = provider_payments(provider, cashfree_payment(order, status=status))

        assert payment.outcome == outcome

    def test_reads_amount_time_and_reason(self, provider):
        order = factories.GatewayOrderFactory.build(amount=Decimal("10.01"))

        (payment,) = provider_payments(
            provider, cashfree_payment(order, "77", status="FAILED", error="Debit failed")
        )

        assert payment.payment_id == "77"
        assert payment.amount == Decimal("10.01")
        assert payment.started_at == datetime.fromisoformat("2026-10-18T10:15:06+05:30")
        assert payment.occurred_at == datetime.fromisoformat("2026-10-18T10:15:06+05:30")
        assert payment.failure_reason == "Debit failed"
        # The raw attempt is kept as JSON-safe data for the order's payload.
        assert payment.raw["payment_amount"] == "10.01"

    def test_asks_for_the_order_by_its_escaped_id(self, provider, cashfree_api):
        provider.fetch_payments("ORD/1")

        (sent,) = cashfree_api.requests
        assert (sent.method, sent.url) == (
            "GET",
            "https://sandbox.cashfree.com/pg/orders/ORD%2F1/payments",
        )

    def test_order_with_no_attempts_has_no_payments(self, provider):
        assert provider.fetch_payments("ORD-1") == []

    @pytest.mark.parametrize(
        "error",
        [
            requests.ReadTimeout(),
            FakeResponse(404, {"code": "order_not_found"}),
            FakeResponse(200, {}),
        ],
        ids=["timeout", "unknown-order", "not-a-list"],
    )
    def test_lookup_failures_become_gateway_error(self, provider, cashfree_api, error):
        cashfree_api.error = error

        with pytest.raises(GatewayError):
            provider.fetch_payments("ORD-1")


class TestGetProvider:
    def test_cashfree_when_configured(self, cashfree_gateway):
        assert type(cashfree_gateway) is CashfreeProvider
        assert cashfree_gateway.code == GatewayProvider.CASHFREE
        assert cashfree_gateway.environment == "sandbox"
        assert cashfree_gateway.key_id == ""


# ---------------------------------------------------------------------------- services


@pytest.mark.django_db
class TestCreateCashfreeOrder:
    def test_receipt_is_the_cashfree_order_id_and_the_session_is_kept(
        self, cashfree_order, cashfree_api, loan
    ):
        assert cashfree_order.provider == GatewayProvider.CASHFREE
        assert cashfree_order.provider_order_id.startswith(f"{cashfree_order.receipt}-")
        assert cashfree_order.checkout_token == (
            f"{CASHFREE_SESSION_PREFIX}{cashfree_order.provider_order_id}"
        )
        body = cashfree_api.requests[0].json
        assert body["customer_details"]["customer_id"] == loan.customer.customer_code
        assert body["customer_details"]["customer_phone"] == loan.customer.phone
        assert body["order_tags"]["loan_number"] == loan.loan_number
        assert body["order_tags"]["receipt"] == cashfree_order.receipt

    def test_gateway_outage_leaves_nothing_behind(
        self, cashfree_gateway, cashfree_api, raise_order, agent, loan
    ):
        cashfree_api.error = requests.ConnectTimeout()

        with pytest.raises(GatewayError):
            raise_order(agent, loan)

        assert not GatewayOrder.objects.exists()


@pytest.mark.django_db
class TestRefreshOrder:
    def test_captured_payment_issues_the_receipt(self, cashfree_order, cashfree_api, agent):
        cashfree_api.pay(cashfree_order, cashfree_payment(cashfree_order, "5114910000001"))

        order, _ = services.refresh_order(agent, cashfree_order)

        assert order.status == GatewayOrder.Status.PAID
        assert order.provider_payment_id == "5114910000001"
        assert order.paid_at == datetime.fromisoformat("2026-10-18T10:15:06+05:30")
        assert order.raw_payload["source"] == "status_check"
        collection = order.collection
        assert (collection.mode, collection.amount) == (Collection.Mode.UPI, Decimal("5000.00"))
        assert collection.gateway_payment_id == "5114910000001"
        assert AuditLog.objects.filter(
            action=AuditAction.GATEWAY_PAYMENT_CAPTURED, entity_id=str(order.pk)
        ).exists()

    def test_paid_order_is_not_looked_up_again(self, cashfree_order, cashfree_api, agent):
        cashfree_api.pay(cashfree_order, cashfree_payment(cashfree_order))
        services.refresh_order(agent, cashfree_order)
        calls = len(cashfree_api.requests)

        again, _ = services.refresh_order(agent, GatewayOrder.objects.get(pk=cashfree_order.pk))

        assert again.status == GatewayOrder.Status.PAID
        assert len(cashfree_api.requests) == calls
        assert Collection.objects.count() == 1

    def test_payment_in_progress_leaves_the_order_waiting(
        self, cashfree_order, cashfree_api, agent
    ):
        cashfree_api.pay(cashfree_order, cashfree_payment(cashfree_order, status="NOT_ATTEMPTED"))

        order, _ = services.refresh_order(agent, cashfree_order)

        assert order.status == GatewayOrder.Status.CREATED
        assert not Collection.objects.exists()

    def test_no_attempt_yet_leaves_the_order_waiting(self, cashfree_order, agent):
        assert (
            services.refresh_order(agent, cashfree_order)[0].status == GatewayOrder.Status.CREATED
        )

    def test_every_attempt_failed_marks_the_order_failed_once(
        self, cashfree_order, cashfree_api, agent
    ):
        dropped = cashfree_payment(
            cashfree_order, "1", status="USER_DROPPED", at="2026-10-18T10:00:00+05:30"
        )
        declined = cashfree_payment(
            cashfree_order,
            "2",
            status="FAILED",
            error="Debit failed",
            at="2026-10-18T10:05:00+05:30",
        )
        cashfree_api.pay(cashfree_order, dropped, declined)

        order, _ = services.refresh_order(agent, cashfree_order)
        services.refresh_order(agent, order)

        assert order.status == GatewayOrder.Status.FAILED
        assert order.failure_reason == "Debit failed"
        assert (
            AuditLog.objects.filter(
                action=AuditAction.GATEWAY_PAYMENT_FAILED, entity_id=str(order.pk)
            ).count()
            == 1
        )

    def test_retry_in_flight_after_a_failure_is_reported_as_in_progress(
        self, cashfree_order, cashfree_api, agent
    ):
        cashfree_api.pay(cashfree_order, cashfree_payment(cashfree_order, "1", status="FAILED"))
        services.refresh_order(agent, cashfree_order)
        cashfree_api.pay(
            cashfree_order,
            cashfree_payment(cashfree_order, "1", status="FAILED"),
            cashfree_payment(cashfree_order, "2", status="PENDING"),
        )

        order, in_progress = services.refresh_order(
            agent, GatewayOrder.objects.get(pk=cashfree_order.pk)
        )

        assert order.status == GatewayOrder.Status.FAILED
        assert in_progress

    def test_nothing_in_flight_once_paid_or_failed(self, cashfree_order, cashfree_api, agent):
        cashfree_api.pay(cashfree_order, cashfree_payment(cashfree_order, "1", status="FAILED"))
        _, after_failure = services.refresh_order(agent, cashfree_order)
        cashfree_api.pay(cashfree_order, cashfree_payment(cashfree_order, "2"))
        _, after_capture = services.refresh_order(
            agent, GatewayOrder.objects.get(pk=cashfree_order.pk)
        )

        assert (after_failure, after_capture) == (False, False)

    def test_abandoned_attempts_do_not_hold_a_later_failure_open(
        self, cashfree_order, cashfree_api, agent
    ):
        # Cashfree leaves an abandoned QR PENDING, with a completion time once it expires.
        abandoned = cashfree_payment(
            cashfree_order, "1", status="PENDING", at="2026-10-18T10:00:00+05:30"
        )
        abandoned["payment_completion_time"] = "2026-10-18T10:02:00+05:30"
        declined = cashfree_payment(
            cashfree_order,
            "2",
            status="FAILED",
            error="Debit failed",
            at="2026-10-18T10:05:00+05:30",
        )
        cashfree_api.pay(cashfree_order, abandoned, declined)

        order, in_progress = services.refresh_order(agent, cashfree_order)

        assert order.status == GatewayOrder.Status.FAILED
        assert not in_progress

    def test_expired_pending_attempt_is_not_in_progress(self, cashfree_order, cashfree_api, agent):
        expired = cashfree_payment(cashfree_order, "1", status="PENDING")
        expired["payment_completion_time"] = "2026-10-18T10:17:06+05:30"
        cashfree_api.pay(cashfree_order, expired)

        order, in_progress = services.refresh_order(agent, cashfree_order)

        assert order.status == GatewayOrder.Status.CREATED
        assert not in_progress

    def test_failed_attempt_with_another_in_flight_is_not_a_failure(
        self, cashfree_order, cashfree_api, agent
    ):
        cashfree_api.pay(
            cashfree_order,
            cashfree_payment(cashfree_order, "1", status="FAILED"),
            cashfree_payment(cashfree_order, "2", status="PENDING"),
        )

        assert (
            services.refresh_order(agent, cashfree_order)[0].status == GatewayOrder.Status.CREATED
        )

    def test_retry_after_a_failure_can_still_pay(self, cashfree_order, cashfree_api, agent):
        cashfree_api.pay(cashfree_order, cashfree_payment(cashfree_order, "1", status="FAILED"))
        services.refresh_order(agent, cashfree_order)
        cashfree_api.pay(
            cashfree_order,
            cashfree_payment(cashfree_order, "1", status="FAILED"),
            cashfree_payment(cashfree_order, "2"),
        )

        order, _ = services.refresh_order(agent, GatewayOrder.objects.get(pk=cashfree_order.pk))

        assert order.status == GatewayOrder.Status.PAID
        assert order.provider_payment_id == "2"
        assert order.failure_reason == ""

    def test_amount_that_does_not_match_the_order_is_refused(
        self, cashfree_order, cashfree_api, agent
    ):
        cashfree_api.pay(cashfree_order, cashfree_payment(cashfree_order, amount=Decimal("1.00")))

        with pytest.raises(PaymentAmountMismatch):
            services.refresh_order(agent, cashfree_order)

        assert not Collection.objects.exists()

    def test_payment_the_loan_can_no_longer_take_is_kept_for_refund(
        self, cashfree_order, cashfree_api, agent, loan
    ):
        loan.amount_paid = loan.total_payable - Decimal("100.00")
        loan.save(update_fields=["amount_paid"])
        cashfree_api.pay(cashfree_order, cashfree_payment(cashfree_order))

        order, _ = services.refresh_order(agent, cashfree_order)

        assert order.status == GatewayOrder.Status.REFUND_DUE
        assert order.collection is None

    def test_gateway_outage_changes_nothing(self, cashfree_order, cashfree_api, agent):
        cashfree_api.error = requests.ConnectTimeout()

        with pytest.raises(GatewayError):
            services.refresh_order(agent, cashfree_order)

        cashfree_order.refresh_from_db()
        assert cashfree_order.status == GatewayOrder.Status.CREATED

    def test_order_from_an_inactive_gateway_is_refused(self, cashfree_gateway, agent, loan):
        mock_order = factories.GatewayOrderFactory(loan=loan, agent=agent)

        with pytest.raises(Exception) as excinfo:
            services.refresh_order(agent, mock_order)

        assert excinfo.value.code == "GATEWAY_MISMATCH"

    def test_mock_gateway_reports_nothing_new(self, order, agent):
        assert services.refresh_order(agent, order)[0].status == GatewayOrder.Status.CREATED


@pytest.mark.django_db
class TestSyncOpenOrders:
    def test_picks_up_payments_whose_webhook_was_lost(
        self, cashfree_gateway, cashfree_api, raise_order, agent, loan
    ):
        paid = raise_order(agent, loan, "1000.00")
        waiting = raise_order(agent, loan, "2000.00")
        expired = raise_order(agent, loan, "500.00")
        GatewayOrder.objects.filter(pk=expired.pk).update(status=GatewayOrder.Status.EXPIRED)
        cashfree_api.pay(paid, cashfree_payment(paid, "1"))
        cashfree_api.pay(expired, cashfree_payment(expired, "3"))

        changed = services.sync_open_orders()

        assert sorted(o.pk for o in changed) == sorted([paid.pk, expired.pk])
        waiting.refresh_from_db()
        assert waiting.status == GatewayOrder.Status.CREATED

    def test_skips_old_orders_and_other_gateways(self, cashfree_gateway, cashfree_api, agent, loan):
        old = factories.GatewayOrderFactory(
            provider=GatewayProvider.CASHFREE, loan=loan, agent=agent
        )
        GatewayOrder.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=2))
        factories.GatewayOrderFactory(loan=loan, agent=agent)

        assert services.sync_open_orders() == []
        assert cashfree_api.requests == []

    def test_one_order_failing_does_not_stop_the_rest(
        self, cashfree_gateway, cashfree_api, raise_order, agent, loan
    ):
        mismatched = raise_order(agent, loan, "1000.00")
        paid = raise_order(agent, loan, "2000.00")
        cashfree_api.pay(mismatched, cashfree_payment(mismatched, "1", amount=Decimal("1.00")))
        cashfree_api.pay(paid, cashfree_payment(paid, "2"))

        changed = services.sync_open_orders()

        assert [o.pk for o in changed] == [paid.pk]

    def test_command_reports_what_changed(self, cashfree_order, cashfree_api, capsys):
        cashfree_api.pay(cashfree_order, cashfree_payment(cashfree_order))

        call_command("sync_gateway_orders")

        assert "Updated 1 UPI order(s)." in capsys.readouterr().out


@pytest.mark.django_db
class TestWebhookService:
    def handle(self, raw: bytes, timestamp: str = TIMESTAMP):
        return services.handle_webhook(
            raw_body=raw, signature=cashfree_sign(raw, timestamp), timestamp=timestamp
        )

    def test_success_and_status_check_record_the_payment_once(
        self, cashfree_order, cashfree_api, agent
    ):
        self.handle(cashfree_webhook_body("PAYMENT_SUCCESS_WEBHOOK", cashfree_order, "9"))
        cashfree_api.pay(cashfree_order, cashfree_payment(cashfree_order, "9"))

        order, _ = services.refresh_order(agent, GatewayOrder.objects.get(pk=cashfree_order.pk))

        assert order.status == GatewayOrder.Status.PAID
        assert Collection.objects.count() == 1

    def test_redelivery_to_a_second_endpoint_is_a_duplicate(self, cashfree_order):
        raw = cashfree_webhook_body("PAYMENT_SUCCESS_WEBHOOK", cashfree_order, "9")
        self.handle(raw)

        # Same event signed at another time, e.g. from both notify_url and the dashboard.
        _, duplicate = self.handle(raw, timestamp="1792224099999")

        assert duplicate
        assert WebhookEvent.objects.count() == 1


# ---------------------------------------------------------------------------- the API


@pytest.mark.django_db
class TestCashfreeApi:
    def test_order_carries_the_checkout_session(
        self, agent_client, loan, idempotency_headers, cashfree_gateway
    ):
        response = agent_client.post(
            ORDERS_URL, {"loan_id": loan.pk, "amount": "1500.00"}, format="json",
            **idempotency_headers(),
        )  # fmt: skip

        assert response.status_code == 201, response.json()
        body = response.json()
        checkout = body["checkout"]
        assert checkout["provider"] == "CASHFREE"
        assert checkout["environment"] == "sandbox"
        assert checkout["key_id"] == ""
        assert checkout["checkout_script"] == "https://sdk.cashfree.com/js/v3/cashfree.js"
        assert checkout["order_id"] == body["order"]["provider_order_id"]
        assert checkout["order_id"].startswith(body["order"]["receipt"])
        assert checkout["session_id"] == f"{CASHFREE_SESSION_PREFIX}{checkout['order_id']}"
        assert CASHFREE_SECRET_KEY not in json.dumps(body)

    def test_mock_checkout_has_no_session(self, agent_client, loan, idempotency_headers):
        response = agent_client.post(
            ORDERS_URL, {"loan_id": loan.pk, "amount": "1500.00"}, format="json",
            **idempotency_headers(),
        )  # fmt: skip

        assert response.json()["checkout"]["session_id"] == ""

    def test_config_reports_cashfree_without_secrets(self, agent_client, cashfree_gateway):
        body = agent_client.get(CONFIG_URL).json()

        assert body["provider"] == "CASHFREE"
        assert body["environment"] == "sandbox"
        assert body["key_id"] == ""
        assert CASHFREE_SECRET_KEY not in json.dumps(body)
        assert CASHFREE_APP_ID not in json.dumps(body)

    def test_refresh_issues_the_receipt(self, agent_client, cashfree_order, cashfree_api):
        cashfree_api.pay(cashfree_order, cashfree_payment(cashfree_order, "5114910000001"))

        response = agent_client.post(refresh_url(cashfree_order))

        assert response.status_code == 200, response.json()
        body = response.json()
        assert body["order"]["status"] == "PAID"
        assert body["receipt"]["mode"] == "UPI"
        assert body["receipt"]["gateway_payment_id"] == "5114910000001"

    def test_refresh_while_paying_returns_the_waiting_order(
        self, agent_client, cashfree_order, cashfree_api
    ):
        cashfree_api.pay(cashfree_order, cashfree_payment(cashfree_order, status="PENDING"))

        response = agent_client.post(refresh_url(cashfree_order))

        assert response.status_code == 200
        assert response.json()["order"]["status"] == "CREATED"
        assert response.json()["receipt"] is None
        assert response.json()["payment_in_progress"] is True

    def test_manager_can_check_a_branch_order(self, manager_client, cashfree_order, cashfree_api):
        cashfree_api.pay(cashfree_order, cashfree_payment(cashfree_order))

        response = manager_client.post(refresh_url(cashfree_order))

        assert response.status_code == 200
        assert response.json()["order"]["status"] == "PAID"
        # The receipt still belongs to the agent who raised the order.
        assert Collection.objects.get().agent_id == cashfree_order.agent_id

    def test_another_agents_order_is_not_found(self, client_for, other_agent, cashfree_order):
        assert client_for(other_agent).post(refresh_url(cashfree_order)).status_code == 404

    def test_refresh_requires_authentication(self, api_client, cashfree_order):
        assert api_client.post(refresh_url(cashfree_order)).status_code == 401

    def test_refresh_during_an_outage_is_a_502(self, agent_client, cashfree_order, cashfree_api):
        cashfree_api.error = requests.ReadTimeout()

        response = agent_client.post(refresh_url(cashfree_order))

        assert response.status_code == 502
        assert error_code(response) == "GATEWAY_ERROR"

    def test_checkout_signature_route_cannot_confirm_cashfree(self, agent_client, cashfree_order):
        response = agent_client.post(
            VERIFY_URL,
            {"order_id": cashfree_order.provider_order_id, "payment_id": "1", "signature": "x"},
            format="json",
        )

        assert response.status_code == 400
        assert error_code(response) == "INVALID_SIGNATURE"
        assert not Collection.objects.exists()


@pytest.mark.django_db
class TestCashfreeWebhookApi:
    def post(self, client, raw: bytes, *, signature: str | None = None, timestamp=TIMESTAMP):
        return client.generic(
            "POST",
            WEBHOOK_URL,
            raw,
            content_type="application/json",
            HTTP_X_WEBHOOK_SIGNATURE=(
                cashfree_sign(raw, timestamp) if signature is None else signature
            ),
            HTTP_X_WEBHOOK_TIMESTAMP=timestamp,
            HTTP_X_WEBHOOK_VERSION="2026-01-01",
        )

    def test_signed_success_is_applied_without_authentication(self, api_client, cashfree_order):
        raw = cashfree_webhook_body("PAYMENT_SUCCESS_WEBHOOK", cashfree_order, "5114910000001")

        response = self.post(api_client, raw)

        assert response.status_code == 200, response.json()
        assert response.json() == {
            "event_id": "PAYMENT_SUCCESS_WEBHOOK:5114910000001",
            "status": "processed",
        }
        cashfree_order.refresh_from_db()
        assert cashfree_order.status == GatewayOrder.Status.PAID
        assert cashfree_order.collection.gateway_payment_id == "5114910000001"

    def test_redelivery_is_acknowledged_as_duplicate(self, api_client, cashfree_order):
        raw = cashfree_webhook_body("PAYMENT_SUCCESS_WEBHOOK", cashfree_order)
        self.post(api_client, raw)

        response = self.post(api_client, raw)

        assert response.json()["status"] == "duplicate"
        assert Collection.objects.count() == 1

    def test_user_dropped_marks_the_order_failed(self, api_client, cashfree_order):
        raw = cashfree_webhook_body("PAYMENT_USER_DROPPED_WEBHOOK", cashfree_order)

        assert self.post(api_client, raw).json()["status"] == "processed"

        cashfree_order.refresh_from_db()
        assert cashfree_order.status == GatewayOrder.Status.FAILED
        assert cashfree_order.failure_reason == USER_DROPPED_REASON

    def test_amount_mismatch_is_kept_for_follow_up(self, api_client, cashfree_order):
        raw = cashfree_webhook_body(
            "PAYMENT_SUCCESS_WEBHOOK", cashfree_order, amount=Decimal("1.00")
        )

        response = self.post(api_client, raw)

        assert response.status_code == 200
        assert response.json()["status"] == "failed"
        assert WebhookEvent.objects.get().error.startswith("PAYMENT_AMOUNT_MISMATCH")

    @pytest.mark.parametrize(
        ("signature", "timestamp"),
        [("bm90LWl0", TIMESTAMP), ("", TIMESTAMP), (None, "")],
        ids=["forged", "unsigned", "no-timestamp"],
    )
    def test_unverified_delivery_is_a_400(self, api_client, cashfree_order, signature, timestamp):
        raw = cashfree_webhook_body("PAYMENT_SUCCESS_WEBHOOK", cashfree_order)
        if signature is None:
            signature = cashfree_sign(raw, TIMESTAMP)

        response = self.post(api_client, raw, signature=signature, timestamp=timestamp)

        assert response.status_code == 400
        assert error_code(response) == "INVALID_SIGNATURE"
        assert not WebhookEvent.objects.exists()

    def test_non_ascii_signature_is_a_400(self, api_client, cashfree_order):
        raw = cashfree_webhook_body("PAYMENT_SUCCESS_WEBHOOK", cashfree_order)

        response = self.post(api_client, raw, signature="\xe9t\xe9")

        assert response.status_code == 400
        assert error_code(response) == "INVALID_SIGNATURE"

    def test_refused_while_another_gateway_is_active(self, api_client, settings, order):
        settings.PAYMENT_PROVIDER = "mock"
        raw = cashfree_webhook_body("PAYMENT_SUCCESS_WEBHOOK", order)

        response = self.post(api_client, raw)

        assert response.status_code == 400
        assert not WebhookEvent.objects.exists()

    def test_inbox_shows_the_order_and_payment(self, api_client, finance_client, cashfree_order):
        raw = cashfree_webhook_body("PAYMENT_SUCCESS_WEBHOOK", cashfree_order, "5114910000001")
        self.post(api_client, raw)

        (event,) = finance_client.get("/api/payments/webhook-events/").json()["results"]

        assert event["provider"] == "CASHFREE"
        assert event["order_id"] == cashfree_order.provider_order_id
        assert event["payment_id"] == "5114910000001"

    def test_inbox_can_be_filtered_by_cashfree_order(
        self, api_client, finance_client, cashfree_order
    ):
        self.post(api_client, cashfree_webhook_body("PAYMENT_SUCCESS_WEBHOOK", cashfree_order))

        response = finance_client.get(
            "/api/payments/webhook-events/", {"search": cashfree_order.provider_order_id}
        )

        assert response.json()["count"] == 1


def test_get_provider_reads_cashfree_settings(settings):
    settings.PAYMENT_PROVIDER = "cashfree"
    settings.CASHFREE_APP_ID = "app"
    settings.CASHFREE_SECRET_KEY = "secret"
    settings.CASHFREE_ENVIRONMENT = "production"
    settings.CASHFREE_NOTIFY_URL = "https://api.example.com/hook"
    settings.CASHFREE_RETURN_URL = ""

    provider = get_provider()

    assert isinstance(provider, CashfreeProvider)
    assert provider.base_url == "https://api.cashfree.com/pg"
    assert provider.notify_url == "https://api.example.com/hook"
