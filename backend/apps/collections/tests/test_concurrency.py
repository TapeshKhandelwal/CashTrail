import uuid
from decimal import Decimal

import pytest

from apps.collections.models import Collection
from apps.collections.services import record_collection
from apps.core.exceptions import OverCollection
from apps.core.testing.concurrency import run_concurrently

pytestmark = pytest.mark.django_db(transaction=True)


def cash_call(agent, loan, amount, key=None):
    return lambda: record_collection(
        actor=agent,
        loan=loan,
        amount=Decimal(amount),
        mode=Collection.Mode.CASH,
        idempotency_key=key or uuid.uuid4(),
        confirm_duplicate=True,
    )


def test_simultaneous_collections_cannot_exceed_outstanding(agent, loan):
    amount = "60000.00"  # each fits the outstanding balance alone, but not together

    results = run_concurrently(cash_call(agent, loan, amount), cash_call(agent, loan, amount))

    successes = [r for r in results if isinstance(r, tuple)]
    failures = [r for r in results if isinstance(r, Exception)]
    assert len(successes) == 1
    assert len(failures) == 1
    assert isinstance(failures[0], OverCollection)
    loan.refresh_from_db()
    assert loan.amount_paid == Decimal(amount)
    assert Collection.objects.count() == 1


def test_simultaneous_retries_with_one_key_record_once(agent, loan):
    key = uuid.uuid4()

    results = run_concurrently(
        cash_call(agent, loan, "5000.00", key), cash_call(agent, loan, "5000.00", key)
    )

    assert all(isinstance(r, tuple) for r in results), results
    (first, first_replayed), (second, second_replayed) = results
    assert first.pk == second.pk
    assert sorted([first_replayed, second_replayed]) == [False, True]
    loan.refresh_from_db()
    assert loan.amount_paid == Decimal("5000.00")
