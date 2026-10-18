from decimal import Decimal

import pytest
import requests

from apps.audit.models import AuditAction, AuditLog
from apps.collections.models import Collection
from apps.core.testing import factories
from apps.payments import services
from apps.payments.models import GatewayOrder, WebhookEvent

from .helpers import RAZORPAY_WEBHOOK_SECRET, sign, webhook_body

pytestmark = pytest.mark.django_db

ORDERS_URL = "/api/payments/orders/"
VERIFY_URL = "/api/payments/verify/"
CONFIG_URL = "/api/payments/config/"
WEBHOOK_URL = "/api/payments/webhooks/razorpay/"


def mock_pay_url(order):
    return f"/api/payments/mock/{order.pk}/pay/"


def error_code(response) -> str:
    return response.json()["error"]["code"]


class TestCreateOrder:
    def post(self, client, headers, **data):
        return client.post(ORDERS_URL, data, format="json", **headers)

    def test_returns_the_order_and_checkout_options(
        self, agent_client, loan, customer, idempotency_headers
    ):
        response = self.post(agent_client, idempotency_headers(), loan_id=loan.pk, amount="5000.50")

        assert response.status_code == 201, response.json()
        body = response.json()
        assert body["order"]["status"] == "CREATED"
        assert body["order"]["amount"] == "5000.50"
        assert body["order"]["amount_paise"] == 500050
        assert body["order"]["loan_number"] == loan.loan_number
        assert body["order"]["receipt"].startswith("ORD-BLR01-")
        checkout = body["checkout"]
        assert checkout["provider"] == "MOCK"
        assert checkout["key_id"] == ""
        assert checkout["order_id"] == body["order"]["provider_order_id"]
        assert checkout["amount"] == "5000.50"
        assert checkout["amount_paise"] == 500050
        assert checkout["currency"] == "INR"
        assert checkout["prefill"]["name"] == customer.full_name
        assert checkout["prefill"]["contact"] == customer.phone

    def test_retry_with_same_key_replays(self, agent_client, loan, idempotency_headers):
        headers = idempotency_headers()
        first = self.post(agent_client, headers, loan_id=loan.pk, amount="5000.00")
        retry = self.post(agent_client, headers, loan_id=loan.pk, amount="5000.00")

        assert retry.status_code == 200
        assert retry.headers["Idempotent-Replayed"] == "true"
        assert retry.json()["order"]["id"] == first.json()["order"]["id"]

    def test_idempotency_key_is_required(self, agent_client, loan):
        response = agent_client.post(
            ORDERS_URL, {"loan_id": loan.pk, "amount": "5.00"}, format="json"
        )

        assert response.status_code == 400
        assert error_code(response) == "IDEMPOTENCY_KEY_REQUIRED"

    def test_over_collection_is_refused(self, agent_client, loan, idempotency_headers):
        amount = str(loan.outstanding + Decimal("0.01"))
        response = self.post(agent_client, idempotency_headers(), loan_id=loan.pk, amount=amount)

        assert response.status_code == 422
        assert error_code(response) == "OVER_COLLECTION"
        assert response.json()["error"]["details"]["outstanding"] == str(loan.outstanding)

    def test_float_amount_is_refused(self, agent_client, loan, idempotency_headers):
        response = self.post(agent_client, idempotency_headers(), loan_id=loan.pk, amount=10.5)

        assert response.status_code == 400

    def test_loan_outside_scope_is_not_found(
        self, agent_client, other_branch, other_branch_agent, idempotency_headers
    ):
        customer = factories.CustomerFactory(branch=other_branch, assigned_agent=other_branch_agent)
        other_loan = factories.LoanFactory(customer=customer)

        response = self.post(
            agent_client, idempotency_headers(), loan_id=other_loan.pk, amount="100.00"
        )

        assert response.status_code == 404

    @pytest.mark.parametrize("client_name", ["manager_client", "finance_client", "admin_client"])
    def test_only_agents_raise_orders(self, request, client_name, loan, idempotency_headers):
        client = request.getfixturevalue(client_name)

        response = self.post(client, idempotency_headers(), loan_id=loan.pk, amount="100.00")

        assert response.status_code == 403

    def test_razorpay_checkout_carries_the_public_key(
        self, agent_client, loan, idempotency_headers, razorpay_gateway, monkeypatch
    ):
        def create(self, data, **options):
            return {"id": "order_RzpTest000009", "amount": data["amount"], "currency": "INR"}

        monkeypatch.setattr("razorpay.resources.order.Order.create", create)

        response = self.post(agent_client, idempotency_headers(), loan_id=loan.pk, amount="100.00")

        assert response.status_code == 201, response.json()
        checkout = response.json()["checkout"]
        assert checkout["provider"] == "RAZORPAY"
        assert checkout["key_id"] == "rzp_test_cashtrail"
        assert checkout["order_id"] == "order_RzpTest000009"
        assert checkout["checkout_script"].startswith("https://checkout.razorpay.com/")

    def test_gateway_outage_is_a_502(
        self, agent_client, loan, idempotency_headers, razorpay_gateway, monkeypatch
    ):
        def create(self, data, **options):
            raise requests.ConnectTimeout()

        monkeypatch.setattr("razorpay.resources.order.Order.create", create)

        response = self.post(agent_client, idempotency_headers(), loan_id=loan.pk, amount="100.00")

        assert response.status_code == 502
        assert error_code(response) == "GATEWAY_ERROR"
        assert not GatewayOrder.objects.exists()


class TestVerify:
    def test_issues_the_receipt(self, agent_client, order, checkout):
        payment_id, signature = checkout(order)
        data = {
            "order_id": order.provider_order_id,
            "payment_id": payment_id,
            "signature": signature,
        }

        response = agent_client.post(VERIFY_URL, data, format="json")
        retry = agent_client.post(VERIFY_URL, data, format="json")

        assert response.status_code == 201, response.json()
        body = response.json()
        assert body["order"]["status"] == "PAID"
        assert body["order"]["receipt_number"] == body["receipt"]["receipt_number"]
        assert body["receipt"]["mode"] == "UPI"
        assert body["receipt"]["gateway_payment_id"] == payment_id
        assert [s["status"] for s in body["receipt"]["timeline"]] == ["COLLECTED", "SETTLED"]
        assert retry.status_code == 200
        assert retry.headers["Idempotent-Replayed"] == "true"
        assert retry.json()["receipt"]["id"] == body["receipt"]["id"]

    def test_payment_the_loan_can_no_longer_take_is_kept_for_refund(
        self, agent_client, loan, order, checkout
    ):
        GatewayOrder.objects.filter(pk=order.pk).update(status=GatewayOrder.Status.EXPIRED)
        loan.amount_paid = loan.total_payable - Decimal("100.00")
        loan.save(update_fields=["amount_paid"])
        payment_id, signature = checkout(order)

        response = agent_client.post(
            VERIFY_URL,
            {"order_id": order.provider_order_id, "payment_id": payment_id, "signature": signature},
            format="json",
        )

        assert response.status_code == 201, response.json()
        body = response.json()
        assert body["order"]["status"] == "REFUND_DUE"
        assert body["order"]["provider_payment_id"] == payment_id
        assert body["receipt"] is None

    def test_bad_signature_is_a_400(self, agent_client, order, checkout):
        payment_id, _ = checkout(order)

        response = agent_client.post(
            VERIFY_URL,
            {"order_id": order.provider_order_id, "payment_id": payment_id, "signature": "x"},
            format="json",
        )

        assert response.status_code == 400
        assert error_code(response) == "INVALID_SIGNATURE"
        assert not Collection.objects.exists()

    def test_another_agents_order_is_not_found(self, client_for, other_agent, order, checkout):
        payment_id, signature = checkout(order)

        response = client_for(other_agent).post(
            VERIFY_URL,
            {"order_id": order.provider_order_id, "payment_id": payment_id, "signature": signature},
            format="json",
        )

        assert response.status_code == 404


class TestMockPay:
    def test_success_returns_the_receipt(self, agent_client, order):
        response = agent_client.post(mock_pay_url(order), {"outcome": "success"}, format="json")

        assert response.status_code == 200, response.json()
        body = response.json()
        assert body["order"]["status"] == "PAID"
        assert body["receipt"]["mode"] == "UPI"
        assert body["receipt"]["amount"] == "5000.00"

    def test_failure_returns_the_failed_order(self, agent_client, order):
        response = agent_client.post(mock_pay_url(order), {"outcome": "failure"}, format="json")

        assert response.status_code == 200
        assert response.json()["order"]["status"] == "FAILED"
        assert response.json()["receipt"] is None

    def test_not_available_with_razorpay(self, agent_client, order, razorpay_gateway):
        response = agent_client.post(mock_pay_url(order), {}, format="json")

        assert response.status_code == 404

    def test_other_agents_cannot_pay(self, client_for, other_agent, order):
        response = client_for(other_agent).post(mock_pay_url(order), {}, format="json")

        assert response.status_code == 404


class TestRazorpayWebhook:
    def post(self, client, body: bytes, signature: str, event_id: str = "evt_api_1"):
        return client.generic(
            "POST",
            WEBHOOK_URL,
            body,
            content_type="application/json",
            HTTP_X_RAZORPAY_SIGNATURE=signature,
            HTTP_X_RAZORPAY_EVENT_ID=event_id,
        )

    def test_signed_capture_is_applied_without_authentication(
        self, api_client, razorpay_gateway, razorpay_order
    ):
        body = webhook_body("payment.captured", razorpay_order, "pay_RzpTest000001")

        response = self.post(api_client, body, sign(RAZORPAY_WEBHOOK_SECRET, body))

        assert response.status_code == 200, response.json()
        assert response.json() == {"event_id": "evt_api_1", "status": "processed"}
        razorpay_order.refresh_from_db()
        assert razorpay_order.status == GatewayOrder.Status.PAID
        assert razorpay_order.collection.gateway_payment_id == "pay_RzpTest000001"

    def test_redelivery_is_acknowledged_as_duplicate(
        self, api_client, razorpay_gateway, razorpay_order
    ):
        body = webhook_body("payment.captured", razorpay_order, "pay_RzpTest000001")
        signature = sign(RAZORPAY_WEBHOOK_SECRET, body)
        self.post(api_client, body, signature)

        response = self.post(api_client, body, signature)

        assert response.json()["status"] == "duplicate"
        assert Collection.objects.count() == 1

    def test_bad_signature_is_a_400(self, api_client, razorpay_gateway, razorpay_order):
        body = webhook_body("payment.captured", razorpay_order, "pay_RzpTest000001")

        response = self.post(api_client, body, sign("not-the-secret", body))

        assert response.status_code == 400
        assert error_code(response) == "INVALID_SIGNATURE"
        assert not WebhookEvent.objects.exists()

    def test_unapplied_event_is_acknowledged_as_failed(
        self, api_client, razorpay_gateway, razorpay_order
    ):
        body = webhook_body(
            "payment.captured", razorpay_order, "pay_RzpTest000001", amount=Decimal("1.00")
        )

        response = self.post(api_client, body, sign(RAZORPAY_WEBHOOK_SECRET, body))

        assert response.status_code == 200
        assert response.json()["status"] == "failed"
        assert WebhookEvent.objects.get().error.startswith("PAYMENT_AMOUNT_MISMATCH")


class TestListOrders:
    @pytest.fixture
    def orders(self, agent, other_agent, loan, branch, other_branch, other_branch_agent):
        other_agent_loan = factories.LoanFactory(
            customer=factories.CustomerFactory(branch=branch, assigned_agent=other_agent)
        )
        other_branch_loan = factories.LoanFactory(
            customer=factories.CustomerFactory(
                branch=other_branch, assigned_agent=other_branch_agent
            )
        )
        return {
            "mine": factories.GatewayOrderFactory(loan=loan, agent=agent),
            "colleague": factories.GatewayOrderFactory(loan=other_agent_loan),
            "other_branch": factories.GatewayOrderFactory(loan=other_branch_loan),
        }

    def ids(self, client, **params):
        response = client.get(ORDERS_URL, params)
        assert response.status_code == 200, response.json()
        return {row["id"] for row in response.json()["results"]}

    def test_agent_sees_own_orders(self, agent_client, orders):
        assert self.ids(agent_client) == {orders["mine"].pk}

    def test_manager_sees_branch_orders(self, manager_client, orders):
        assert self.ids(manager_client) == {orders["mine"].pk, orders["colleague"].pk}

    def test_finance_sees_everything(self, finance_client, orders):
        assert self.ids(finance_client) == {o.pk for o in orders.values()}

    def test_filters_by_status(self, finance_client, orders):
        GatewayOrder.objects.filter(pk=orders["mine"].pk).update(status="FAILED")

        assert self.ids(finance_client, status="FAILED") == {orders["mine"].pk}

    def test_order_outside_scope_is_not_found(self, agent_client, orders):
        response = agent_client.get(f"{ORDERS_URL}{orders['colleague'].pk}/")

        assert response.status_code == 404

    def test_list_requires_authentication(self, api_client):
        assert api_client.get(ORDERS_URL).status_code == 401

    def test_list_query_count_does_not_grow_with_rows(
        self, finance_client, orders, loan, django_assert_max_num_queries
    ):
        factories.GatewayOrderFactory.create_batch(6, loan=loan)

        # Request savepoint pair, auth user, page count and rows.
        with django_assert_max_num_queries(6):
            assert finance_client.get(ORDERS_URL).json()["count"] == 9


class TestConfig:
    def test_mock_gateway(self, agent_client):
        response = agent_client.get(CONFIG_URL)

        assert response.status_code == 200
        assert response.json() == {
            "provider": "MOCK",
            "key_id": "",
            "environment": "test",
            "currency": "INR",
            "checkout_script": "",
            "checkout_timeout_seconds": 900,
        }

    def test_razorpay_exposes_only_the_public_key(self, agent_client, razorpay_gateway):
        body = agent_client.get(CONFIG_URL).json()

        assert body["provider"] == "RAZORPAY"
        assert body["key_id"] == "rzp_test_cashtrail"
        assert "test_key_secret" not in str(body)


class TestWebhookEvents:
    URL = "/api/payments/webhook-events/"

    LATE_ORDER_ID = "order_Late00000001"

    @pytest.fixture
    def stuck_payment(self, mock_gateway, loan, agent):
        """A capture that arrived before its order was stored, so it could not be applied."""
        unknown = factories.GatewayOrderFactory.build(
            loan=loan, agent=agent, provider_order_id=self.LATE_ORDER_ID
        )
        body = webhook_body("payment.captured", unknown, "pay_Stuck0000001")
        services.handle_webhook(raw_body=body, signature=mock_gateway.sign_webhook(body))
        return WebhookEvent.objects.get()

    def test_unapplied_events_are_listed_for_follow_up(self, finance_client, stuck_payment):
        response = finance_client.get(self.URL, {"processed": "false"})

        assert response.status_code == 200
        (event,) = response.json()["results"]
        assert event["error"].startswith("NOT_FOUND")
        assert (event["order_id"], event["payment_id"]) == (self.LATE_ORDER_ID, "pay_Stuck0000001")
        assert finance_client.get(self.URL, {"processed": "true"}).json()["count"] == 0

    def test_retry_records_the_payment_once_the_cause_is_fixed(
        self, finance_client, finance_user, stuck_payment, loan, agent
    ):
        order = factories.GatewayOrderFactory(
            loan=loan, agent=agent, provider_order_id=self.LATE_ORDER_ID
        )

        response = finance_client.post(f"{self.URL}{stuck_payment.pk}/retry/")

        assert response.status_code == 200, response.json()
        assert response.json()["processed_at"] is not None
        order.refresh_from_db()
        assert order.status == GatewayOrder.Status.PAID
        entry = AuditLog.objects.get(action=AuditAction.GATEWAY_PAYMENT_CAPTURED)
        assert entry.actor == finance_user

    def test_retry_that_fails_again_keeps_the_error(self, finance_client, stuck_payment):
        response = finance_client.post(f"{self.URL}{stuck_payment.pk}/retry/")

        assert response.status_code == 200
        assert response.json()["processed_at"] is None
        assert response.json()["error"].startswith("NOT_FOUND")

    def test_list_query_count_does_not_grow_with_rows(
        self, finance_client, django_assert_max_num_queries
    ):
        factories.WebhookEventFactory.create_batch(8)

        with django_assert_max_num_queries(6):
            assert finance_client.get(self.URL).json()["count"] == 8

    def test_applied_event_cannot_be_retried(self, finance_client, mock_gateway, order):
        body = webhook_body("payment.captured", order, "pay_Done00000001")
        event, _ = services.handle_webhook(raw_body=body, signature=mock_gateway.sign_webhook(body))

        response = finance_client.post(f"{self.URL}{event.pk}/retry/")

        assert response.status_code == 409
        assert error_code(response) == "INVALID_STATE_TRANSITION"

    @pytest.mark.parametrize("client_name", ["agent_client", "manager_client"])
    def test_only_admin_and_finance_see_the_inbox(self, request, client_name, stuck_payment):
        client = request.getfixturevalue(client_name)

        assert client.get(self.URL).status_code == 403
        assert client.post(f"{self.URL}{stuck_payment.pk}/retry/").status_code == 403
