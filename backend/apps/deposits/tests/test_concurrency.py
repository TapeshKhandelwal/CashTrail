import uuid
from decimal import Decimal

import pytest

from apps.core.dates import business_date
from apps.core.testing.concurrency import run_concurrently
from apps.deposits import services
from apps.deposits.models import BankDeposit

pytestmark = pytest.mark.django_db(transaction=True)


def test_simultaneous_deposit_retries_with_one_key_record_once(manager, bank_account, branch_cash):
    submission = branch_cash()
    key = uuid.uuid4()

    def deposit():
        return services.create_deposit(
            manager,
            submission_ids=[submission.pk],
            bank_account_id=bank_account.pk,
            deposited_amount=submission.received_amount,
            deposit_date=business_date(),
            reference_number="SLIP-0001",
            idempotency_key=key,
        )

    results = run_concurrently(deposit, deposit)

    assert all(isinstance(result, tuple) for result in results), results
    (first, first_created), (second, second_created) = results
    assert first.pk == second.pk
    assert sorted([first_created, second_created]) == [False, True]
    assert BankDeposit.objects.count() == 1


@pytest.mark.usefixtures("gateway_bank_account")
def test_simultaneous_settlement_retries_with_one_key_record_once(finance_user, upi_payments):
    payments = upi_payments("1000.00", "500.00")
    key = uuid.uuid4()

    def settle():
        return services.record_gateway_settlement(
            finance_user,
            collection_ids=[payment.pk for payment in payments],
            gross_amount=Decimal("1500.00"),
            fee_amount=Decimal("30.00"),
            tax_amount=Decimal("5.40"),
            net_amount=Decimal("1464.60"),
            utr="UTR0000001",
            settled_on=business_date(),
            idempotency_key=key,
        )

    results = run_concurrently(settle, settle)

    assert all(isinstance(result, tuple) for result in results), results
    assert results[0][0].pk == results[1][0].pk
    assert sorted(created for _, created in results) == [False, True]
    assert BankDeposit.objects.count() == 1
