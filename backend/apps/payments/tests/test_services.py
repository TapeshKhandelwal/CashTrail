import json
import uuid
from datetime import timedelta
from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.audit.models import AuditAction, AuditLog
from apps.collections.models import Collection
from apps.collections.services import record_collection
from apps.core.exceptions import (
    IdempotencyConflict,
    InvalidStateTransition,
    OverCollection,
    ResourceNotFound,
    ScopeViolation,
    ValidationFailed,
)
from apps.core.testing import factories
from apps.customers.services import assign_customer
from apps.loans.models import Loan
from apps.payments import services
from apps.payments.exceptions import InvalidSignature, OrderAlreadyPaid
from apps.payments.models import CHECKOUT_WINDOW, GatewayOrder, WebhookEvent

from .helpers import webhook_body

pytestmark = pytest.mark.django_db


def audit_actions(entity) -> list[str]:
    return list(
        AuditLog.objects.filter(
            entity_type=entity._meta.model_name, entity_id=str(entity.pk)
        ).values_list("action", flat=True)
    )


class TestCreateOrder:
    def test_creates_an_order_awaiting_payment(self, agent, loan, branch):
        order, created = services.create_order(
            agent, loan=loan, amount=Decimal("5000.00"), idempotency_key=uuid.uuid4()
        )

        assert created
        assert order.status == GatewayOrder.Status.CREATED
        assert order.provider == "MOCK"
        assert order.provider_order_id.startswith("order_")
        assert order.receipt.startswith("ORD-BLR01-")
        assert order.raw_payload["amount"] == 500000
        entry = AuditLog.objects.get(action=AuditAction.GATEWAY_ORDER_CREATED)
        assert entry.entity_id == str(order.pk)
        assert entry.branch_id == branch.pk
        assert entry.after["amount"] == "5000.00"

    def test_retry_with_same_key_returns_the_order(self, agent, loan):
        key = uuid.uuid4()
        first, _ = services.create_order(agent, loan=loan, amount="5000.00", idempotency_key=key)
        again, created = services.create_order(
            agent, loan=loan, amount="5000.00", idempotency_key=key
        )

        assert not created
        assert again.pk == first.pk
        assert GatewayOrder.objects.count() == 1

    def test_key_reuse_with_another_amount_is_refused(self, agent, loan):
        key = uuid.uuid4()
        services.create_order(agent, loan=loan, amount="5000.00", idempotency_key=key)

        with pytest.raises(IdempotencyConflict):
            services.create_order(agent, loan=loan, amount="6000.00", idempotency_key=key)

    def test_amount_above_outstanding_is_refused(self, agent, loan):
        with pytest.raises(OverCollection) as excinfo:
            services.create_order(
                agent, loan=loan, amount=loan.outstanding + 1, idempotency_key=uuid.uuid4()
            )
        assert excinfo.value.details["outstanding"] == str(loan.outstanding)
        assert not GatewayOrder.objects.exists()

    def test_open_orders_reserve_their_amount(self, agent, loan, raise_order):
        raise_order(agent, loan, "60000.00")

        with pytest.raises(OverCollection) as excinfo:
            raise_order(agent, loan, "50000.00")
        assert excinfo.value.details["awaiting_payment"] == "60000.00"
        assert raise_order(agent, loan, "40000.00").status == GatewayOrder.Status.CREATED

    def test_reservation_lapses_after_the_checkout_window(self, agent, loan, raise_order):
        stale = raise_order(agent, loan, "60000.00")
        GatewayOrder.objects.filter(pk=stale.pk).update(
            created_at=timezone.now() - CHECKOUT_WINDOW - timedelta(seconds=1)
        )

        assert raise_order(agent, loan, "50000.00").pk != stale.pk

    def test_same_amount_while_open_returns_the_open_order(self, agent, loan, raise_order):
        first = raise_order(agent, loan, "5000.00")
        order, created = services.create_order(
            agent, loan=loan, amount="5000.00", idempotency_key=uuid.uuid4()
        )

        assert not created
        assert order.pk == first.pk

    def test_only_the_assigned_agent_can_raise_orders(self, other_agent, loan, manager):
        for actor in (other_agent, manager):
            with pytest.raises(ScopeViolation):
                services.create_order(
                    actor, loan=loan, amount="100.00", idempotency_key=uuid.uuid4()
                )

    def test_closed_loan_is_refused(self, agent, loan):
        Loan.objects.filter(pk=loan.pk).update(
            status=Loan.Status.CLOSED, amount_paid=loan.total_payable, closed_at=timezone.now()
        )

        with pytest.raises(ValidationFailed) as excinfo:
            services.create_order(agent, loan=loan, amount="100.00", idempotency_key=uuid.uuid4())
        assert excinfo.value.code == "LOAN_NOT_ACTIVE"


class TestVerifyPayment:
    def test_records_a_upi_collection_with_a_receipt(self, agent, loan, order, checkout):
        payment_id, signature = checkout(order)

        paid, replayed = services.verify_payment(
            agent,
            provider_order_id=order.provider_order_id,
            payment_id=payment_id,
            signature=signature,
        )

        assert not replayed
        collection = paid.collection
        assert collection.mode == Collection.Mode.UPI
        assert collection.status == Collection.Status.COLLECTED
        assert collection.receipt_number.startswith("RCT-BLR01-")
        assert collection.amount == Decimal("5000.00")
        assert collection.agent == agent
        assert collection.gateway_payment_id == payment_id
        assert collection.idempotency_key is None
        assert collection.allocations.count() == 1
        order.refresh_from_db()
        assert order.status == GatewayOrder.Status.PAID
        assert order.collection == collection
        assert order.provider_payment_id == payment_id
        assert order.paid_at == collection.collected_at
        loan.refresh_from_db()
        assert loan.amount_paid == Decimal("5000.00")
        assert AuditAction.GATEWAY_PAYMENT_CAPTURED in audit_actions(order)
        assert AuditAction.COLLECTION_RECORDED in audit_actions(collection)

    def test_verifying_twice_replays_the_receipt(self, agent, order, checkout):
        payment_id, signature = checkout(order)
        params = {
            "provider_order_id": order.provider_order_id,
            "payment_id": payment_id,
            "signature": signature,
        }

        first, _ = services.verify_payment(agent, **params)
        again, replayed = services.verify_payment(agent, **params)

        assert replayed
        assert again.pk == first.pk
        assert Collection.objects.count() == 1

    def test_bad_signature_records_nothing(self, agent, order, checkout):
        payment_id, _ = checkout(order)

        with pytest.raises(InvalidSignature):
            services.verify_payment(
                agent,
                provider_order_id=order.provider_order_id,
                payment_id=payment_id,
                signature="0" * 64,
            )
        assert not Collection.objects.exists()
        order.refresh_from_db()
        assert order.status == GatewayOrder.Status.CREATED

    def test_signature_is_checked_against_the_stored_order(
        self, agent, loan, order, raise_order, checkout
    ):
        other = raise_order(agent, loan, "1000.00")
        payment_id, signature_for_other = checkout(other)

        with pytest.raises(InvalidSignature):
            services.verify_payment(
                agent,
                provider_order_id=order.provider_order_id,
                payment_id=payment_id,
                signature=signature_for_other,
            )

    def test_another_agents_order_is_not_found(self, other_agent, order, checkout):
        payment_id, signature = checkout(order)

        with pytest.raises(ResourceNotFound):
            services.verify_payment(
                other_agent,
                provider_order_id=order.provider_order_id,
                payment_id=payment_id,
                signature=signature,
            )

    def test_second_payment_on_a_paid_order_is_refused(self, agent, order, checkout, mock_gateway):
        payment_id, signature = checkout(order)
        services.verify_payment(
            agent,
            provider_order_id=order.provider_order_id,
            payment_id=payment_id,
            signature=signature,
        )
        other_payment = "pay_Second000001"

        with pytest.raises(OrderAlreadyPaid):
            services.verify_payment(
                agent,
                provider_order_id=order.provider_order_id,
                payment_id=other_payment,
                signature=mock_gateway.sign_checkout(order.provider_order_id, other_payment),
            )
        assert Collection.objects.count() == 1


class TestMockPay:
    def test_success_goes_through_verification(self, agent, order):
        paid = services.mock_pay(agent, order_id=order.pk, outcome="success")

        assert paid.status == GatewayOrder.Status.PAID
        assert paid.collection.mode == Collection.Mode.UPI
        assert services.mock_pay(agent, order_id=order.pk, outcome="success").collection_id == (
            paid.collection_id
        )

    def test_failure_marks_the_order_failed_and_allows_a_retry(self, agent, order):
        failed = services.mock_pay(agent, order_id=order.pk, outcome="failure")

        assert failed.status == GatewayOrder.Status.FAILED
        assert failed.failed_at is not None
        assert failed.failure_reason
        assert not Collection.objects.exists()
        assert AuditAction.GATEWAY_PAYMENT_FAILED in audit_actions(order)

        retried = services.mock_pay(agent, order_id=order.pk, outcome="success")
        assert retried.status == GatewayOrder.Status.PAID

    def test_failing_a_paid_order_is_refused(self, agent, order):
        services.mock_pay(agent, order_id=order.pk, outcome="success")

        with pytest.raises(InvalidStateTransition):
            services.mock_pay(agent, order_id=order.pk, outcome="failure")

    def test_unavailable_with_a_real_gateway(self, agent, order, razorpay_gateway):
        with pytest.raises(ResourceNotFound):
            services.mock_pay(agent, order_id=order.pk, outcome="success")

    def test_another_agents_order_is_not_found(self, other_agent, order):
        with pytest.raises(ResourceNotFound):
            services.mock_pay(other_agent, order_id=order.pk, outcome="success")


class TestHandleWebhook:
    @pytest.fixture
    def deliver(self, mock_gateway):
        def send(body: bytes, event_id: str = "evt_1", signature: str | None = None):
            return services.handle_webhook(
                raw_body=body,
                signature=mock_gateway.sign_webhook(body) if signature is None else signature,
                event_id=event_id,
            )

        return send

    def test_capture_records_the_collection(self, deliver, order, loan):
        event, duplicate = deliver(webhook_body("payment.captured", order, "pay_Hook00000001"))

        assert not duplicate
        assert event.processed_at is not None
        assert event.error == ""
        order.refresh_from_db()
        assert order.status == GatewayOrder.Status.PAID
        assert order.collection.gateway_payment_id == "pay_Hook00000001"
        assert order.collection.agent_id == order.agent_id
        entry = AuditLog.objects.get(action=AuditAction.GATEWAY_PAYMENT_CAPTURED)
        assert entry.actor is None
        loan.refresh_from_db()
        assert loan.amount_paid == order.amount

    def test_duplicate_delivery_is_ignored(self, deliver, order):
        body = webhook_body("payment.captured", order, "pay_Hook00000001")
        deliver(body)

        _, duplicate = deliver(body)

        assert duplicate
        assert WebhookEvent.objects.count() == 1
        assert Collection.objects.count() == 1

    def test_order_paid_after_payment_captured_records_once(self, deliver, order):
        deliver(webhook_body("payment.captured", order, "pay_Hook00000001"), event_id="evt_1")
        event, duplicate = deliver(
            webhook_body("order.paid", order, "pay_Hook00000001"), event_id="evt_2"
        )

        assert not duplicate
        assert event.processed_at is not None
        assert WebhookEvent.objects.count() == 2
        assert Collection.objects.count() == 1

    def test_webhook_after_checkout_verification_records_once(
        self, deliver, agent, order, checkout
    ):
        payment_id, signature = checkout(order)
        services.verify_payment(
            agent,
            provider_order_id=order.provider_order_id,
            payment_id=payment_id,
            signature=signature,
        )

        event, _ = deliver(webhook_body("payment.captured", order, payment_id))

        assert event.processed_at is not None
        assert Collection.objects.count() == 1

    def test_payment_failed_marks_the_order_failed(self, deliver, order):
        deliver(webhook_body("payment.failed", order, "pay_Fail00000001", error="Declined"))

        order.refresh_from_db()
        assert order.status == GatewayOrder.Status.FAILED
        assert order.failure_reason == "Declined"
        assert not Collection.objects.exists()

    def test_late_failure_does_not_touch_a_paid_order(self, deliver, order):
        deliver(webhook_body("payment.captured", order, "pay_Hook00000001"), event_id="evt_1")
        event, _ = deliver(
            webhook_body("payment.failed", order, "pay_Fail00000001"), event_id="evt_2"
        )

        assert event.processed_at is not None
        order.refresh_from_db()
        assert order.status == GatewayOrder.Status.PAID

    def test_bad_signature_is_rejected_before_storing(self, deliver, order):
        with pytest.raises(InvalidSignature):
            deliver(webhook_body("payment.captured", order, "pay_X"), signature="f" * 64)
        assert not WebhookEvent.objects.exists()

    def test_body_must_be_a_json_object(self, deliver):
        with pytest.raises(ValidationFailed):
            deliver(b"[1, 2]")

    def test_unknown_order_is_kept_for_follow_up(self, deliver, order):
        order.provider_order_id = "order_Unknown00001"
        event, _ = deliver(webhook_body("payment.captured", order, "pay_X"))

        assert event.processed_at is None
        assert event.error.startswith("NOT_FOUND")

    def test_amount_mismatch_is_not_recorded(self, deliver, order):
        body = webhook_body("payment.captured", order, "pay_X", amount=Decimal("1.00"))

        event, _ = deliver(body)

        assert event.processed_at is None
        assert event.error.startswith("PAYMENT_AMOUNT_MISMATCH")
        assert not Collection.objects.exists()

    def test_failed_event_is_retried_on_redelivery(self, deliver, agent, loan):
        order = factories.GatewayOrderFactory.build(loan=loan, agent=agent)
        body = webhook_body("payment.captured", order, "pay_Retry0000001")
        first, _ = deliver(body)
        assert first.error.startswith("NOT_FOUND")

        order.save()
        retried, duplicate = deliver(body)

        assert not duplicate
        assert retried.pk == first.pk
        assert retried.processed_at is not None
        assert retried.error == ""
        assert Collection.objects.count() == 1

    def test_capture_without_a_payment_id_is_kept_for_follow_up(self, deliver, order):
        body = json.loads(webhook_body("payment.captured", order, "pay_Dropped00001"))
        del body["payload"]["payment"]["entity"]["id"]

        event, _ = deliver(json.dumps(body).encode(), event_id="evt_no_payment")

        assert event.processed_at is None
        assert event.error.startswith("VALIDATION_FAILED")
        assert not Collection.objects.exists()

    def test_unhandled_event_types_are_acknowledged(self, deliver, order):
        body = json.dumps({"event": "refund.processed", "payload": {}}).encode()

        event, _ = deliver(body, event_id="evt_refund")

        assert event.processed_at is not None


class TestExpireStaleOrders:
    def test_command_expires_stale_orders(self, agent, loan, raise_order):
        stale = raise_order(agent, loan, "1000.00")
        GatewayOrder.objects.filter(pk=stale.pk).update(
            created_at=timezone.now() - CHECKOUT_WINDOW - timedelta(minutes=1)
        )
        out = StringIO()

        call_command("expire_gateway_orders", stdout=out)

        stale.refresh_from_db()
        assert stale.status == GatewayOrder.Status.EXPIRED
        assert "Expired 1 unpaid UPI order(s)." in out.getvalue()

    def test_expires_unpaid_orders_past_the_checkout_window(self, agent, loan, raise_order):
        stale = raise_order(agent, loan, "1000.00")
        fresh = raise_order(agent, loan, "2000.00")
        declined = raise_order(agent, loan, "3000.00")
        services.mock_pay(agent, order_id=declined.pk, outcome="failure")
        GatewayOrder.objects.filter(pk__in=[stale.pk, declined.pk]).update(
            created_at=timezone.now() - CHECKOUT_WINDOW - timedelta(minutes=1)
        )

        expired = services.expire_stale_orders()

        assert [order.pk for order in expired] == [stale.pk]
        stale.refresh_from_db()
        fresh.refresh_from_db()
        assert stale.status == GatewayOrder.Status.EXPIRED
        assert fresh.status == GatewayOrder.Status.CREATED
        declined.refresh_from_db()
        assert declined.status == GatewayOrder.Status.FAILED
        assert AuditAction.GATEWAY_ORDER_EXPIRED in audit_actions(stale)
        assert services.expire_stale_orders() == []

    def test_late_capture_of_an_expired_order_is_still_recorded(self, agent, order, checkout, loan):
        GatewayOrder.objects.filter(pk=order.pk).update(
            created_at=timezone.now() - CHECKOUT_WINDOW - timedelta(minutes=1)
        )
        services.expire_stale_orders()
        payment_id, signature = checkout(order)

        paid, _ = services.verify_payment(
            agent,
            provider_order_id=order.provider_order_id,
            payment_id=payment_id,
            signature=signature,
        )

        order.refresh_from_db()
        assert order.status == GatewayOrder.Status.PAID
        assert order.collection == paid.collection


class TestCaptureAfterTheLoanChanged:
    """The gateway already holds the money, so a capture is never refused."""

    @pytest.fixture
    def pay_in_cash(self, agent):
        def make(loan, amount):
            collection, _ = record_collection(
                actor=agent,
                loan=loan,
                amount=Decimal(amount),
                mode=Collection.Mode.CASH,
                idempotency_key=uuid.uuid4(),
                confirm_duplicate=True,
            )
            return collection

        return make

    @staticmethod
    def expire(order):
        GatewayOrder.objects.filter(pk=order.pk).update(
            created_at=timezone.now() - CHECKOUT_WINDOW - timedelta(minutes=1)
        )
        services.expire_stale_orders()

    def test_cash_cannot_use_the_amount_an_open_order_awaits(self, loan, order, pay_in_cash):
        with pytest.raises(OverCollection) as excinfo:
            pay_in_cash(loan, loan.outstanding)

        assert excinfo.value.details["awaiting_payment"] == "5000.00"
        pay_in_cash(loan, loan.outstanding - order.amount)
        loan.refresh_from_db()
        assert loan.outstanding == order.amount

    def test_late_capture_after_the_loan_was_paid_off_is_due_for_refund(
        self, agent, loan, order, checkout, pay_in_cash, mock_gateway
    ):
        self.expire(order)
        pay_in_cash(loan, loan.outstanding)
        payment_id, signature = checkout(order)

        paid, replayed = services.verify_payment(
            agent,
            provider_order_id=order.provider_order_id,
            payment_id=payment_id,
            signature=signature,
        )

        assert not replayed
        assert paid.status == GatewayOrder.Status.REFUND_DUE
        assert paid.collection is None
        assert paid.provider_payment_id == payment_id
        assert paid.paid_at is not None
        assert paid.failure_reason.startswith("Refund the customer")
        assert not Collection.objects.filter(mode=Collection.Mode.UPI).exists()
        loan.refresh_from_db()
        assert (loan.status, loan.outstanding) == (Loan.Status.CLOSED, 0)
        assert AuditAction.GATEWAY_PAYMENT_REFUND_DUE in audit_actions(order)

        body = webhook_body("payment.captured", order, payment_id)
        event, _ = services.handle_webhook(raw_body=body, signature=mock_gateway.sign_webhook(body))
        assert (event.processed_at is not None, event.error) == (True, "")

    def test_late_capture_larger_than_the_balance_is_due_for_refund(
        self, deliver_capture, loan, order, pay_in_cash
    ):
        self.expire(order)
        pay_in_cash(loan, loan.outstanding - Decimal("100.00"))

        event = deliver_capture(order, "pay_TooLate000001")

        order.refresh_from_db()
        assert event.processed_at is not None
        assert order.status == GatewayOrder.Status.REFUND_DUE
        loan.refresh_from_db()
        assert loan.outstanding == Decimal("100.00")

    def test_refund_due_order_replays_its_payment_and_refuses_another(
        self, agent, loan, order, checkout, pay_in_cash, deliver_capture
    ):
        self.expire(order)
        pay_in_cash(loan, loan.outstanding)
        payment_id, signature = checkout(order)
        params = {
            "provider_order_id": order.provider_order_id,
            "payment_id": payment_id,
            "signature": signature,
        }
        services.verify_payment(agent, **params)

        again, replayed = services.verify_payment(agent, **params)
        other = deliver_capture(order, "pay_Other0000001")

        assert replayed
        assert again.status == GatewayOrder.Status.REFUND_DUE
        assert other.error.startswith("ORDER_ALREADY_PAID")

    def test_capture_after_the_customer_was_reassigned_is_recorded(
        self, deliver_capture, manager, other_agent, agent, loan, order
    ):
        assign_customer(manager, loan.customer, other_agent)

        event = deliver_capture(order, "pay_Reassigned01")

        assert event.processed_at is not None
        order.refresh_from_db()
        assert order.status == GatewayOrder.Status.PAID
        assert order.collection.agent == agent
        loan.refresh_from_db()
        assert loan.amount_paid == order.amount

    @pytest.fixture
    def deliver_capture(self, mock_gateway):
        def make(order, payment_id):
            body = webhook_body("payment.captured", order, payment_id)
            event, _ = services.handle_webhook(
                raw_body=body, signature=mock_gateway.sign_webhook(body)
            )
            return event

        return make
