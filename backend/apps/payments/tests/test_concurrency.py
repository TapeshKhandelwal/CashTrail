import pytest

from apps.collections.models import Collection
from apps.core.testing.concurrency import run_concurrently
from apps.payments import services
from apps.payments.models import GatewayOrder, WebhookEvent

from .helpers import webhook_body

pytestmark = pytest.mark.django_db(transaction=True)


def test_checkout_and_webhook_racing_record_one_collection(agent, order, checkout, mock_gateway):
    payment_id, signature = checkout(order)
    body = webhook_body("payment.captured", order, payment_id)

    results = run_concurrently(
        lambda: services.verify_payment(
            agent,
            provider_order_id=order.provider_order_id,
            payment_id=payment_id,
            signature=signature,
        ),
        lambda: services.handle_webhook(
            raw_body=body, signature=mock_gateway.sign_webhook(body), event_id="evt_race"
        ),
    )

    assert not [r for r in results if isinstance(r, Exception)], results
    (paid, _), (event, _) = results
    assert Collection.objects.get().pk == paid.collection_id
    assert event.processed_at is not None
    order.refresh_from_db()
    assert order.status == GatewayOrder.Status.PAID
    assert order.collection_id == paid.collection_id
    order.loan.refresh_from_db()
    assert order.loan.amount_paid == order.amount


def test_simultaneous_redeliveries_apply_once(order, mock_gateway):
    body = webhook_body("payment.captured", order, "pay_Race00000001")

    def deliver():
        return services.handle_webhook(
            raw_body=body, signature=mock_gateway.sign_webhook(body), event_id="evt_dup"
        )

    results = run_concurrently(deliver, deliver, deliver)

    assert not [r for r in results if isinstance(r, Exception)], results
    assert sorted(duplicate for _, duplicate in results) == [False, True, True]
    assert WebhookEvent.objects.count() == 1
    assert Collection.objects.count() == 1
