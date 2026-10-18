import threading
import uuid
from decimal import Decimal
from functools import partial

import pytest
from django.db import connection

from apps.core.exceptions import DomainError
from apps.core.testing.concurrency import run_concurrently
from apps.reconciliation import services
from apps.reconciliation.models import CashSubmission, Discrepancy


@pytest.mark.django_db(transaction=True)
def test_concurrent_reviews_settle_on_exactly_one_outcome(manager, admin_user, pending_submission):
    barrier = threading.Barrier(2)
    outcomes = []

    def review(action):
        try:
            barrier.wait()
            action()
            outcomes.append("ok")
        except DomainError as exc:
            outcomes.append(exc.code)
        finally:
            connection.close()

    approve = partial(
        services.approve_submission,
        manager,
        pending_submission,
        received_amount=Decimal("48500.00"),
        reason_code=Discrepancy.ReasonCode.AGENT_SHORTAGE,
        remarks="Short.",
    )
    reject = partial(services.reject_submission, admin_user, pending_submission, reason="Recount.")
    threads = [threading.Thread(target=review, args=(action,)) for action in (approve, reject)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(outcomes) == ["INVALID_STATE_TRANSITION", "ok"]
    pending_submission.refresh_from_db()
    assert pending_submission.status != CashSubmission.Status.SUBMITTED
    assert Discrepancy.objects.count() == (pending_submission.status != "REJECTED")


@pytest.mark.django_db(transaction=True)
def test_simultaneous_submission_retries_with_one_key_record_once(agent, receive_cash):
    receipts = receive_cash("3000.00", "2000.00")
    key = uuid.uuid4()

    def submit():
        return services.create_submission(
            agent,
            collection_ids=[receipt.pk for receipt in receipts],
            declared_amount=Decimal("5000.00"),
            idempotency_key=key,
        )

    results = run_concurrently(submit, submit)

    assert all(isinstance(result, tuple) for result in results), results
    (first, first_created), (second, second_created) = results
    assert first.pk == second.pk
    assert sorted([first_created, second_created]) == [False, True]
    assert CashSubmission.objects.count() == 1
