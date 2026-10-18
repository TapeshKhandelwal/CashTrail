import pytest

from apps.collections.models import Collection
from apps.core.exceptions import InvalidStateTransition
from apps.deposits.models import BankDeposit
from apps.reconciliation.models import CashSubmission


def test_cash_collection_follows_branch_path():
    collection = Collection(mode=Collection.Mode.CASH, status=Collection.Status.COLLECTED)

    assert collection.can_transition_to(Collection.Status.SUBMITTED)
    assert not collection.can_transition_to(Collection.Status.SETTLED)


def test_upi_collection_settles_directly():
    collection = Collection(mode=Collection.Mode.UPI, status=Collection.Status.COLLECTED)

    assert collection.allowed_transitions() == {Collection.Status.SETTLED}


def test_transition_to_sets_status():
    submission = CashSubmission(status=CashSubmission.Status.SUBMITTED)

    submission.transition_to(CashSubmission.Status.REJECTED)

    assert submission.status == CashSubmission.Status.REJECTED
    assert submission.is_locked


def test_illegal_transition_raises_conflict():
    deposit = BankDeposit(pk=7, status=BankDeposit.Status.SETTLED)

    with pytest.raises(InvalidStateTransition) as excinfo:
        deposit.transition_to(BankDeposit.Status.FAILED)

    assert excinfo.value.status_code == 409
    assert excinfo.value.details == {
        "entity": "bankdeposit",
        "id": 7,
        "from": "SETTLED",
        "to": "FAILED",
    }
