"""The database refuses to rewrite reconciled history, even through raw SQL."""

from contextlib import contextmanager
from decimal import Decimal

import pytest
from django.db import DatabaseError, connection, transaction
from django.urls import path
from django.utils import timezone
from rest_framework.decorators import api_view

from apps.audit.models import AuditLog
from apps.collections.models import Collection
from apps.core.testing import factories
from apps.deposits.models import BankDeposit
from apps.reconciliation.models import CashSubmission, Discrepancy, SubmissionItem

pytestmark = pytest.mark.django_db


def run_sql(sql, params):
    with connection.cursor() as cursor:
        cursor.execute(sql, params)


@contextmanager
def locked():
    """Expect a trigger rejection; the savepoint keeps the test transaction usable."""
    with pytest.raises(DatabaseError, match="RECORD_LOCKED"), transaction.atomic():
        yield


@pytest.fixture
def deposited_collection(loan, manager):
    submission = factories.CashSubmissionFactory(agent=loan.customer.assigned_agent, approved=True)
    deposit = factories.BankDepositFactory(branch=loan.branch, created_by=manager)
    return factories.CollectionFactory(
        loan=loan,
        status=Collection.Status.DEPOSITED,
        submission=submission,
        deposit=deposit,
    )


def test_audit_log_is_append_only():
    entry = factories.AuditLogFactory()

    with locked():
        run_sql("UPDATE audit_auditlog SET action = 'TAMPERED' WHERE id = %s", [entry.pk])
    with locked():
        run_sql("DELETE FROM audit_auditlog WHERE id = %s", [entry.pk])


def test_reconciled_collection_amount_is_immutable(deposited_collection):
    with locked():
        run_sql(
            "UPDATE collections_collection SET amount = 1 WHERE id = %s", [deposited_collection.pk]
        )

    deposited_collection.refresh_from_db()
    assert deposited_collection.amount == Decimal("1000.00")


def settle(deposit):
    BankDeposit.objects.filter(pk=deposit.pk).update(
        status=BankDeposit.Status.SETTLED,
        settled_amount=deposit.deposited_amount,
        settled_on=deposit.deposit_date,
        settled_at=timezone.now(),
    )


def test_reconciled_collection_can_still_progress(deposited_collection):
    settle(deposited_collection.deposit)

    deposited_collection.status = Collection.Status.SETTLED
    deposited_collection.settled_at = timezone.now()
    deposited_collection.save()


def test_collection_settles_only_with_a_settled_deposit(deposited_collection):
    with locked():
        Collection.objects.filter(pk=deposited_collection.pk).update(
            status=Collection.Status.SETTLED, settled_at=timezone.now()
        )


def test_settled_collection_is_frozen(deposited_collection):
    settle(deposited_collection.deposit)
    Collection.objects.filter(pk=deposited_collection.pk).update(
        status=Collection.Status.SETTLED, settled_at=timezone.now()
    )

    with locked():
        Collection.objects.filter(pk=deposited_collection.pk).update(
            status=Collection.Status.DEPOSITED
        )
    with locked():
        Collection.objects.filter(pk=deposited_collection.pk).update(settled_at=None)


def test_issued_balance_after_is_immutable(loan):
    collection = factories.CollectionFactory(loan=loan, balance_after=Decimal("50000.00"))

    with locked():
        run_sql(
            "UPDATE collections_collection SET balance_after = 1 WHERE id = %s", [collection.pk]
        )
    with locked():
        run_sql(
            "UPDATE collections_collection SET balance_after = NULL WHERE id = %s",
            [collection.pk],
        )


def test_missing_balance_after_can_be_filled_once(loan):
    collection = factories.CollectionFactory(loan=loan, balance_after=None)

    run_sql("UPDATE collections_collection SET balance_after = 4000 WHERE id = %s", [collection.pk])

    collection.refresh_from_db()
    assert collection.balance_after == Decimal("4000.00")


@pytest.mark.parametrize(
    "status", [Collection.Status.COLLECTED, Collection.Status.SUBMITTED, Collection.Status.VOIDED]
)
def test_deposited_collection_cannot_be_walked_back(deposited_collection, status):
    with locked():
        run_sql(
            "UPDATE collections_collection SET status = %s, submission_id = NULL, "
            "deposit_id = NULL, voided_at = now() WHERE id = %s",
            [status, deposited_collection.pk],
        )


def test_received_collection_cannot_be_rewound_and_edited(deposited_collection):
    """The rewind-then-edit sequence: back to the agent, change the amount, move forward."""
    pk = deposited_collection.pk
    with locked():
        run_sql(
            "UPDATE collections_collection SET status = 'BRANCH_RECEIVED', deposit_id = NULL, "
            "deposited_at = NULL WHERE id = %s",
            [pk],
        )
    BankDeposit.objects.filter(pk=deposited_collection.deposit_id).update(
        status=BankDeposit.Status.FAILED, failed_at=timezone.now(), failure_reason="Slip lost."
    )
    run_sql(
        "UPDATE collections_collection SET status = 'BRANCH_RECEIVED', deposit_id = NULL, "
        "deposited_at = NULL WHERE id = %s",
        [pk],
    )
    with locked():
        run_sql(
            "UPDATE collections_collection SET status = 'COLLECTED', submission_id = NULL "
            "WHERE id = %s",
            [pk],
        )
    with locked():
        run_sql("UPDATE collections_collection SET amount = 1 WHERE id = %s", [pk])

    deposited_collection.refresh_from_db()
    assert deposited_collection.status == Collection.Status.BRANCH_RECEIVED
    assert deposited_collection.amount == Decimal("1000.00")


def test_received_collection_cannot_skip_ahead_or_change_links(deposited_collection, manager):
    other = factories.BankDepositFactory(branch=deposited_collection.branch, created_by=manager)

    with locked():
        Collection.objects.filter(pk=deposited_collection.pk).update(deposit=other)
    with locked():
        Collection.objects.filter(pk=deposited_collection.pk).update(
            submission=factories.CashSubmissionFactory(
                agent=deposited_collection.agent, approved=True
            )
        )


def test_cash_receipt_cannot_skip_the_branch(loan):
    collection = factories.CollectionFactory(loan=loan)
    deposit = factories.BankDepositFactory(branch=loan.branch, settled=True)

    with locked():
        Collection.objects.filter(pk=collection.pk).update(
            status=Collection.Status.SETTLED, deposit=deposit, settled_at=timezone.now()
        )


def test_upi_receipt_settles_only_through_a_settlement(loan):
    collection = factories.CollectionFactory(loan=loan, upi=True)
    settlement = factories.BankDepositFactory(gateway=True, settled=True)

    with locked():
        Collection.objects.filter(pk=collection.pk).update(status=Collection.Status.VOIDED)
    Collection.objects.filter(pk=collection.pk).update(
        status=Collection.Status.SETTLED, deposit=settlement, settled_at=timezone.now()
    )


def test_submitted_collection_returns_only_from_a_rejected_submission(agent, loan):
    submission = factories.CashSubmissionFactory(agent=agent)
    collection = factories.CollectionFactory(
        loan=loan, status=Collection.Status.SUBMITTED, submission=submission
    )
    SubmissionItem.objects.create(submission=submission, collection=collection)

    with locked():
        Collection.objects.filter(pk=collection.pk).update(
            status=Collection.Status.COLLECTED, submission=None
        )
    with locked():
        Collection.objects.filter(pk=collection.pk).update(status=Collection.Status.BRANCH_RECEIVED)

    CashSubmission.objects.filter(pk=submission.pk).update(
        status=CashSubmission.Status.REJECTED,
        reviewed_at=timezone.now(),
        rejection_reason="Wrong bundle.",
    )
    Collection.objects.filter(pk=collection.pk).update(
        status=Collection.Status.COLLECTED, submission=None, submitted_at=None
    )


def test_rejected_receipt_keeps_its_amount(agent, loan):
    submission = factories.CashSubmissionFactory(agent=agent, rejected=True)
    collection = factories.CollectionFactory(loan=loan)
    SubmissionItem.objects.create(submission=submission, collection=collection)

    with locked():
        run_sql("UPDATE collections_collection SET amount = 1 WHERE id = %s", [collection.pk])
    with locked():
        Collection.objects.filter(pk=collection.pk).update(loan=factories.LoanFactory())


def test_unsubmitted_collection_amount_is_editable_by_services(loan):
    collection = factories.CollectionFactory(loan=loan)

    Collection.objects.filter(pk=collection.pk).update(amount=Decimal("900.00"))


def test_collections_are_never_deleted(loan):
    collection = factories.CollectionFactory(loan=loan)

    with locked():
        run_sql("DELETE FROM collections_collection WHERE id = %s", [collection.pk])


def test_reviewed_submission_is_locked_but_deposit_link_is_writable(agent, manager):
    submission = factories.CashSubmissionFactory(agent=agent, approved=True)

    with locked():
        CashSubmission.objects.filter(pk=submission.pk).update(received_amount=Decimal("1.00"))

    deposit = factories.BankDepositFactory(branch=agent.branch, created_by=manager)
    CashSubmission.objects.filter(pk=submission.pk).update(deposit=deposit)
    CashSubmission.objects.filter(pk=submission.pk).update(deposit=None)


def test_submission_of_a_settled_deposit_cannot_be_detached(agent, manager):
    deposit = factories.BankDepositFactory(branch=agent.branch, created_by=manager, settled=True)
    submission = factories.CashSubmissionFactory(agent=agent, approved=True, deposit=deposit)
    other = factories.BankDepositFactory(branch=agent.branch, created_by=manager)

    with locked():
        run_sql(
            "UPDATE reconciliation_cashsubmission SET deposit_id = NULL WHERE id = %s",
            [submission.pk],
        )
    with locked():
        CashSubmission.objects.filter(pk=submission.pk).update(deposit=other)


def test_closed_discrepancy_keeps_who_was_accountable(agent, other_agent):
    discrepancy = factories.DiscrepancyFactory(
        submission=factories.CashSubmissionFactory(agent=agent, short=True),
        status=Discrepancy.Status.WRITTEN_OFF,
        resolved_at=timezone.now(),
        resolution_notes="Recovered from salary.",
    )

    for change in (
        {"agent": other_agent},
        {"reason_code": Discrepancy.ReasonCode.BANK_ERROR},
        {"notes": "Rewritten."},
        {"raised_by": other_agent},
        {"branch": None},
    ):
        with locked():
            Discrepancy.objects.filter(pk=discrepancy.pk).update(**change)


def test_open_discrepancy_can_still_be_edited(agent):
    discrepancy = factories.DiscrepancyFactory(
        submission=factories.CashSubmissionFactory(agent=agent, short=True)
    )

    Discrepancy.objects.filter(pk=discrepancy.pk).update(notes="Recounted twice.")


def test_submission_items_are_append_only(agent, loan):
    submission = factories.CashSubmissionFactory(agent=agent)
    collection = factories.CollectionFactory(
        loan=loan, status=Collection.Status.SUBMITTED, submission=submission
    )
    item = SubmissionItem.objects.create(submission=submission, collection=collection)

    with locked():
        run_sql(
            "UPDATE reconciliation_submissionitem SET collection_id = collection_id WHERE id = %s",
            [item.pk],
        )
    with locked():
        run_sql("DELETE FROM reconciliation_submissionitem WHERE id = %s", [item.pk])


def test_settled_deposit_is_locked():
    deposit = factories.BankDepositFactory(settled=True)

    with locked():
        BankDeposit.objects.filter(pk=deposit.pk).update(reference_number="OTHER")
    with locked():
        BankDeposit.objects.filter(pk=deposit.pk).update(status=BankDeposit.Status.PENDING)


def test_pending_deposit_can_be_settled():
    deposit = factories.BankDepositFactory()

    BankDeposit.objects.filter(pk=deposit.pk).update(
        status=BankDeposit.Status.SETTLED,
        settled_amount=deposit.deposited_amount,
        settled_on=deposit.deposit_date,
        settled_at=timezone.now(),
    )


def test_allocations_and_installments_are_never_deleted(loan):
    allocation = factories.AllocationFactory(collection=factories.CollectionFactory(loan=loan))

    with locked():
        run_sql("DELETE FROM collections_allocation WHERE id = %s", [allocation.pk])
    with locked():
        run_sql("DELETE FROM loans_installment WHERE id = %s", [allocation.installment_id])


def test_allocation_reversal_is_allowed_but_amount_is_not(loan):
    allocation = factories.AllocationFactory(collection=factories.CollectionFactory(loan=loan))

    allocation.reversed_at = timezone.now()
    allocation.save(update_fields=["reversed_at"])
    with locked():
        run_sql("UPDATE collections_allocation SET amount = 1 WHERE id = %s", [allocation.pk])


@api_view(["POST"])
def tamper_with_audit_log(request, pk):
    run_sql("DELETE FROM audit_auditlog WHERE id = %s", [pk])


urlpatterns = [path("api/tamper/<int:pk>/", tamper_with_audit_log)]


@pytest.mark.urls(__name__)
def test_trigger_error_in_a_request_returns_409(admin_client):
    entry = factories.AuditLogFactory()

    res = admin_client.post(f"/api/tamper/{entry.pk}/")

    assert res.status_code == 409
    assert res.json()["error"]["code"] == "RECORD_LOCKED"
    assert AuditLog.objects.filter(pk=entry.pk).exists()
