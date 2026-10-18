import threading
import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from apps.audit.models import AuditAction, AuditLog
from apps.collections.models import Collection
from apps.core.dates import business_date
from apps.core.exceptions import (
    DomainError,
    DuplicateBankReference,
    IdempotencyConflict,
    InvalidStateTransition,
    RecordLocked,
    ResourceNotFound,
    ScopeViolation,
    ValidationFailed,
)
from apps.core.testing import factories
from apps.deposits import services
from apps.deposits.exceptions import SubmissionAlreadyDeposited
from apps.deposits.models import BankAccount, BankDeposit
from apps.reconciliation.models import Discrepancy

pytestmark = pytest.mark.django_db

TODAY = business_date


def deposit_cash(actor, submissions, bank_account, **overrides):
    params = {
        "submission_ids": [s.pk for s in submissions],
        "bank_account_id": bank_account.pk,
        "deposited_amount": sum(s.received_amount or s.expected_amount for s in submissions),
        "deposit_date": TODAY(),
        "reference_number": "SLIP-0001",
        "remarks": "",
        "idempotency_key": uuid.uuid4(),
        **overrides,
    }
    return services.create_deposit(actor, **params)


def settle(actor, deposit, **overrides):
    params = {
        "settled_amount": deposit.deposited_amount,
        "settled_on": TODAY(),
        "settlement_reference": "STMT-42",
        **overrides,
    }
    return services.settle_deposit(actor, deposit, **params)


def gateway_settle(actor, collections=None, **overrides):
    params = {
        "collection_ids": [c.pk for c in collections] if collections is not None else None,
        "gross_amount": Decimal("1500.00"),
        "fee_amount": Decimal("30.00"),
        "tax_amount": Decimal("5.40"),
        "net_amount": Decimal("1464.60"),
        "utr": "UTR0000001",
        "settled_on": TODAY(),
        "idempotency_key": uuid.uuid4(),
        **overrides,
    }
    return services.record_gateway_settlement(actor, **params)


def actions_for(entity):
    return list(
        AuditLog.objects.filter(
            entity_type=entity._meta.model_name, entity_id=str(entity.pk)
        ).values_list("action", flat=True)
    )


# Creating deposits --------------------------------------------------------------------------


class TestCreateDeposit:
    def test_deposits_approved_cash_and_moves_receipts_to_deposited(
        self, manager, bank_account, branch_cash
    ):
        first, second = branch_cash("3000.00", "2000.00"), branch_cash("1500.00")

        deposit, created = deposit_cash(manager, [first, second], bank_account)

        assert created
        assert deposit.status == BankDeposit.Status.PENDING
        assert deposit.source == BankDeposit.Source.CASH
        assert deposit.branch_id == manager.branch_id
        assert deposit.deposit_number == f"DEP-BLR01-{TODAY():%Y%m%d}-001"
        assert deposit.expected_amount == Decimal("6500.00")
        assert deposit.deposited_amount == Decimal("6500.00")
        assert set(deposit.submissions.values_list("pk", flat=True)) == {first.pk, second.pk}
        collections = Collection.objects.filter(submission__in=[first, second])
        assert collections.count() == 3
        for collection in collections:
            assert collection.status == Collection.Status.DEPOSITED
            assert collection.deposit_id == deposit.pk
            assert collection.deposited_at is not None
        entry = AuditLog.objects.get(action=AuditAction.DEPOSIT_CREATED)
        assert entry.actor == manager
        assert entry.branch_id == manager.branch_id
        assert entry.after["expected_amount"] == "6500.00"
        assert sorted(entry.after["submission_ids"]) == sorted([first.pk, second.pk])

    def test_expected_amount_is_cash_actually_received_at_branch(
        self, manager, bank_account, branch_cash
    ):
        short = branch_cash("3000.00", "2000.00", short=True)

        deposit, _ = deposit_cash(manager, [short], bank_account)

        assert deposit.expected_amount == Decimal("4500.00")

    @pytest.mark.parametrize("trait", [{}, {"rejected": True}])
    def test_only_approved_submissions_can_be_deposited(self, manager, agent, bank_account, trait):
        submission = factories.CashSubmissionFactory(agent=agent, **trait)

        with pytest.raises(ValidationFailed) as exc:
            deposit_cash(manager, [submission], bank_account)

        assert exc.value.details == {"submission_ids": [submission.pk]}
        assert not BankDeposit.objects.exists()

    def test_submission_cannot_be_deposited_twice(self, manager, bank_account, branch_cash):
        submission = branch_cash()
        deposit_cash(manager, [submission], bank_account)

        with pytest.raises(SubmissionAlreadyDeposited):
            deposit_cash(manager, [submission], bank_account, reference_number="SLIP-0002")

    def test_manager_cannot_deposit_another_branchs_cash(
        self, other_branch_manager, bank_account, branch_cash
    ):
        submission = branch_cash()

        with pytest.raises(ResourceNotFound) as exc:
            deposit_cash(other_branch_manager, [submission], bank_account)

        assert exc.value.details == {"submission_ids": [submission.pk]}

    def test_admin_can_deposit_for_any_branch_but_not_mix_branches(
        self, admin_user, bank_account, branch_cash, other_branch_loan
    ):
        local = branch_cash()
        remote = branch_cash("700.00", target_loan=other_branch_loan)

        with pytest.raises(ValidationFailed, match="single branch"):
            deposit_cash(admin_user, [local, remote], bank_account)

        deposit, _ = deposit_cash(admin_user, [remote], bank_account)
        assert deposit.branch_id == other_branch_loan.branch_id
        assert deposit.deposit_number.startswith("DEP-MUM01-")

    @pytest.mark.parametrize("role_fixture", ["agent", "finance_user"])
    def test_only_managers_and_admins_create_deposits(
        self, request, role_fixture, bank_account, branch_cash
    ):
        actor = request.getfixturevalue(role_fixture)

        with pytest.raises(ScopeViolation):
            deposit_cash(actor, [branch_cash()], bank_account)

    def test_unknown_submission_is_not_found(self, manager, bank_account):
        with pytest.raises(ResourceNotFound):
            services.create_deposit(
                manager,
                submission_ids=[999_999],
                bank_account_id=bank_account.pk,
                deposited_amount=Decimal("1.00"),
                deposit_date=TODAY(),
                reference_number="X1",
                idempotency_key=uuid.uuid4(),
            )

    @pytest.mark.parametrize(
        "second_reference", ["slip-0001", "  SLIP-0001 ", "slip - 0001", "Slip-\t0001"]
    )
    def test_duplicate_reference_is_case_and_space_insensitive(
        self, manager, bank_account, branch_cash, second_reference
    ):
        deposit_cash(manager, [branch_cash()], bank_account, reference_number="SLIP-0001")

        with pytest.raises(DuplicateBankReference) as exc:
            deposit_cash(manager, [branch_cash()], bank_account, reference_number=second_reference)

        assert exc.value.details["reference_number"] == "SLIP-0001"

    def test_same_reference_is_fine_on_a_different_account(
        self, manager, bank_account, branch_cash
    ):
        other_account = factories.BankAccountFactory()
        deposit_cash(manager, [branch_cash()], bank_account)

        deposit, _ = deposit_cash(manager, [branch_cash()], other_account)

        assert deposit.reference_number == "SLIP-0001"

    def test_database_rejects_duplicate_reference_without_the_service(self, bank_account):
        factories.BankDepositFactory(bank_account=bank_account, reference_number="ab 12")

        with (
            pytest.raises(IntegrityError, match="uniq_bank_deposit_account_reference"),
            transaction.atomic(),
        ):
            factories.BankDepositFactory(bank_account=bank_account, reference_number="AB12")

    def test_mismatch_requires_remarks(self, manager, bank_account, branch_cash):
        submission = branch_cash("3000.00", "2000.00")

        with pytest.raises(ValidationFailed) as exc:
            deposit_cash(manager, [submission], bank_account, deposited_amount=Decimal("4800.00"))

        assert exc.value.details == {
            "expected_amount": "5000.00",
            "deposited_amount": "4800.00",
            "difference": "200.00",
        }
        assert not BankDeposit.objects.exists()

    @pytest.mark.parametrize(
        ("deposited", "direction"),
        [("4800.00", Discrepancy.Direction.SHORT), ("5100.00", Discrepancy.Direction.EXCESS)],
    )
    def test_mismatch_with_remarks_raises_deposit_discrepancy(
        self, manager, bank_account, branch_cash, deposited, direction
    ):
        deposit, _ = deposit_cash(
            manager,
            [branch_cash("3000.00", "2000.00")],
            bank_account,
            deposited_amount=Decimal(deposited),
            remarks="Counted again at the bank counter.",
        )

        discrepancy = Discrepancy.objects.get(deposit=deposit)
        assert discrepancy.kind == Discrepancy.Kind.DEPOSIT_MISMATCH
        assert discrepancy.direction == direction
        assert discrepancy.amount == abs(Decimal("5000.00") - Decimal(deposited))
        assert discrepancy.branch_id == manager.branch_id
        assert discrepancy.notes == "Counted again at the bank counter."
        assert deposit.remarks == "Counted again at the bank counter."
        assert actions_for(discrepancy) == [AuditAction.DISCREPANCY_RAISED]

    def test_deposit_date_cannot_be_in_the_future(self, manager, bank_account, branch_cash):
        with pytest.raises(ValidationFailed, match="future"):
            deposit_cash(
                manager, [branch_cash()], bank_account, deposit_date=TODAY() + timedelta(days=1)
            )

    def test_deposit_date_cannot_precede_the_approval(self, manager, bank_account, branch_cash):
        with pytest.raises(ValidationFailed, match="approved") as exc:
            deposit_cash(
                manager, [branch_cash()], bank_account, deposit_date=TODAY() - timedelta(days=1)
            )

        assert exc.value.details["latest_approval_date"] == TODAY()

    def test_account_must_be_active_and_not_the_gateway(
        self, manager, branch_cash, gateway_bank_account
    ):
        inactive = factories.BankAccountFactory(is_active=False)

        with pytest.raises(ResourceNotFound):
            deposit_cash(manager, [branch_cash()], inactive)
        with pytest.raises(ValidationFailed, match="gateway"):
            deposit_cash(manager, [branch_cash()], gateway_bank_account)

    def test_retry_with_same_key_returns_original_deposit(self, manager, bank_account, branch_cash):
        submission = branch_cash()
        key = uuid.uuid4()
        deposit, _ = deposit_cash(manager, [submission], bank_account, idempotency_key=key)

        replayed, created = deposit_cash(
            manager, [submission], bank_account, idempotency_key=key, reference_number=" slip-0001"
        )

        assert not created
        assert replayed.pk == deposit.pk
        assert BankDeposit.objects.count() == 1

    def test_reusing_key_for_other_submissions_conflicts(self, manager, bank_account, branch_cash):
        key = uuid.uuid4()
        deposit_cash(manager, [branch_cash()], bank_account, idempotency_key=key)
        other = branch_cash()

        with pytest.raises(IdempotencyConflict):
            deposit_cash(
                manager,
                [other],
                bank_account,
                idempotency_key=key,
                deposited_amount=Decimal("5000.00"),
            )
        other.refresh_from_db()
        assert other.deposit is None

    def test_retry_of_a_deposit_that_failed_meanwhile_still_replays(
        self, manager, finance_user, bank_account, branch_cash
    ):
        submission = branch_cash()
        key = uuid.uuid4()
        deposit, _ = deposit_cash(manager, [submission], bank_account, idempotency_key=key)
        services.fail_deposit(finance_user, deposit, reason="Slip rejected.")

        replayed, created = deposit_cash(manager, [submission], bank_account, idempotency_key=key)

        assert (replayed.pk, created) == (deposit.pk, False)

    def test_reusing_key_with_different_payload_conflicts(self, manager, bank_account, branch_cash):
        key = uuid.uuid4()
        deposit_cash(manager, [branch_cash()], bank_account, idempotency_key=key)

        with pytest.raises(IdempotencyConflict):
            deposit_cash(
                manager,
                [branch_cash()],
                bank_account,
                idempotency_key=key,
                reference_number="SLIP-9999",
            )


@pytest.mark.django_db(transaction=True)
def test_concurrent_deposits_of_the_same_cash_let_only_one_through(
    manager, bank_account, branch_cash
):
    submission = branch_cash()
    barrier = threading.Barrier(2)
    outcomes = []

    def attempt(reference):
        try:
            barrier.wait()
            deposit_cash(manager, [submission], bank_account, reference_number=reference)
            outcomes.append("created")
        except DomainError as exc:
            outcomes.append(exc.code)
        finally:
            connection.close()

    threads = [threading.Thread(target=attempt, args=(f"SLIP-{n}",)) for n in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(outcomes) == ["SUBMISSION_ALREADY_DEPOSITED", "created"]
    assert BankDeposit.objects.count() == 1


# Settlement -----------------------------------------------------------------------------------


@pytest.fixture
def pending_deposit(manager, bank_account, branch_cash):
    deposit, _ = deposit_cash(manager, [branch_cash("3000.00", "2000.00")], bank_account)
    return deposit


class TestSettleDeposit:
    def test_exact_settlement(self, finance_user, pending_deposit):
        deposit = settle(finance_user, pending_deposit)

        assert deposit.status == BankDeposit.Status.SETTLED
        assert deposit.settled_amount == Decimal("5000.00")
        assert deposit.settled_by == finance_user
        assert deposit.settled_at is not None
        assert deposit.settlement_reference == "STMT-42"
        for collection in deposit.collections.all():
            assert collection.status == Collection.Status.SETTLED
            assert collection.settled_at is not None
        assert not Discrepancy.objects.exists()
        entry = AuditLog.objects.get(action=AuditAction.DEPOSIT_SETTLED)
        assert entry.before == {"status": "PENDING", "settled_amount": None, "settled_on": None}
        assert entry.after["status"] == "SETTLED"

    def test_mismatch_requires_remarks(self, finance_user, pending_deposit):
        with pytest.raises(ValidationFailed) as exc:
            settle(finance_user, pending_deposit, settled_amount=Decimal("4990.00"))

        assert exc.value.details["difference"] == "10.00"
        pending_deposit.refresh_from_db()
        assert pending_deposit.status == BankDeposit.Status.PENDING

    def test_mismatch_settles_with_discrepancy(self, finance_user, pending_deposit):
        deposit = settle(
            finance_user,
            pending_deposit,
            settled_amount=Decimal("4990.00"),
            remarks="Bank deducted cash handling charges.",
        )

        assert deposit.status == BankDeposit.Status.SETTLED_WITH_MISMATCH
        discrepancy = Discrepancy.objects.get(deposit=deposit)
        assert discrepancy.kind == Discrepancy.Kind.SETTLEMENT_MISMATCH
        assert discrepancy.direction == Discrepancy.Direction.SHORT
        assert discrepancy.amount == Decimal("10.00")
        assert discrepancy.reason_code == Discrepancy.ReasonCode.BANK_ERROR
        assert set(deposit.collections.values_list("status", flat=True)) == {"SETTLED"}
        raised = AuditLog.objects.get(action=AuditAction.DISCREPANCY_RAISED)
        assert raised.after["kind"] == Discrepancy.Kind.SETTLEMENT_MISMATCH
        assert raised.after["notes"] == "Bank deducted cash handling charges."

    def test_mismatch_can_be_classified_as_bank_charges(self, finance_user, pending_deposit):
        settle(
            finance_user,
            pending_deposit,
            settled_amount=Decimal("4882.00"),
            remarks="Cash handling charge of 100 plus 18 GST.",
            reason_code=Discrepancy.ReasonCode.BANK_CHARGES,
        )

        discrepancy = Discrepancy.objects.get(deposit=pending_deposit)
        assert discrepancy.reason_code == Discrepancy.ReasonCode.BANK_CHARGES

    def test_cannot_settle_twice(self, finance_user, pending_deposit):
        settle(finance_user, pending_deposit)

        with pytest.raises(InvalidStateTransition):
            settle(finance_user, pending_deposit)

    def test_settlement_date_bounds(self, finance_user, pending_deposit):
        with pytest.raises(ValidationFailed, match="before"):
            settle(finance_user, pending_deposit, settled_on=TODAY() - timedelta(days=1))
        with pytest.raises(ValidationFailed, match="future"):
            settle(finance_user, pending_deposit, settled_on=TODAY() + timedelta(days=1))

    def test_branch_manager_cannot_confirm_settlement(self, manager, pending_deposit):
        with pytest.raises(ScopeViolation):
            settle(manager, pending_deposit)

    def test_depositor_cannot_confirm_own_deposit(self, admin_user, bank_account, branch_cash):
        deposit, _ = deposit_cash(admin_user, [branch_cash()], bank_account)

        with pytest.raises(ScopeViolation, match="recorded"):
            settle(admin_user, deposit)


class TestFailDeposit:
    def test_failure_returns_cash_to_branch(self, finance_user, pending_deposit):
        submission_ids = list(pending_deposit.submissions.values_list("pk", flat=True))
        collection_ids = list(pending_deposit.collections.values_list("pk", flat=True))

        deposit = services.fail_deposit(finance_user, pending_deposit, reason="Slip bounced.")

        assert deposit.status == BankDeposit.Status.FAILED
        assert deposit.failure_reason == "Slip bounced."
        assert deposit.failed_by == finance_user
        assert not deposit.submissions.exists()
        assert not deposit.collections.exists()
        for collection in Collection.objects.filter(pk__in=collection_ids):
            assert collection.status == Collection.Status.BRANCH_RECEIVED
            assert collection.deposited_at is None
        entry = AuditLog.objects.get(action=AuditAction.DEPOSIT_FAILED)
        assert entry.after["released_submission_ids"] == submission_ids
        assert sorted(entry.after["released_collection_ids"]) == sorted(collection_ids)

    def test_failed_cash_can_be_redeposited(self, manager, finance_user, bank_account, branch_cash):
        submission = branch_cash()
        failed, _ = deposit_cash(manager, [submission], bank_account)
        services.fail_deposit(finance_user, failed, reason="Bank never credited it.")

        redeposit, _ = deposit_cash(manager, [submission], bank_account, reference_number="SLIP-2")

        submission.refresh_from_db()
        assert submission.deposit_id == redeposit.pk
        assert redeposit.deposit_number.endswith("-002")
        assert BankDeposit.objects.get(pk=failed.pk).status == BankDeposit.Status.FAILED
        settle(finance_user, redeposit)
        assert set(redeposit.collections.values_list("status", flat=True)) == {"SETTLED"}

    def test_mismatch_on_a_failed_deposit_is_closed_so_a_redeposit_is_not_double_counted(
        self, manager, finance_user, bank_account, branch_cash
    ):
        submission = branch_cash("10000.00")
        short = {"deposited_amount": Decimal("9800.00"), "remarks": "Two notes torn."}
        failed, _ = deposit_cash(manager, [submission], bank_account, **short)

        services.fail_deposit(finance_user, failed, reason="Bank rejected the slip.")
        redeposit, _ = deposit_cash(
            manager, [submission], bank_account, reference_number="SLIP-2", **short
        )

        first, second = Discrepancy.objects.order_by("pk")
        assert (first.deposit_id, first.status) == (failed.pk, Discrepancy.Status.RESOLVED)
        assert first.resolution_notes == "Deposit failed: Bank rejected the slip."
        assert first.resolved_by == finance_user
        assert (second.deposit_id, second.status) == (redeposit.pk, Discrepancy.Status.OPEN)
        assert AuditAction.DISCREPANCY_RESOLVED in actions_for(first)

    def test_reason_is_required(self, finance_user, pending_deposit):
        with pytest.raises(ValidationFailed):
            services.fail_deposit(finance_user, pending_deposit, reason="   ")

    def test_settled_deposit_cannot_fail(self, finance_user, pending_deposit):
        settle(finance_user, pending_deposit)

        with pytest.raises(InvalidStateTransition):
            services.fail_deposit(finance_user, pending_deposit, reason="Too late.")


# Gateway settlements --------------------------------------------------------------------------


@pytest.mark.usefixtures("gateway_bank_account")
class TestGatewaySettlement:
    def test_settles_upi_payments_net_of_fee_and_tax(self, finance_user, upi_payments):
        payments = upi_payments("1000.00", "500.00")

        settlement, created = gateway_settle(finance_user, payments)

        assert created
        assert settlement.source == BankDeposit.Source.GATEWAY
        assert settlement.branch is None
        assert settlement.bank_account.is_gateway
        assert settlement.deposit_number == f"DEP-GATEWAY-{TODAY():%Y%m%d}-001"
        assert settlement.status == BankDeposit.Status.SETTLED
        assert settlement.expected_amount == Decimal("1500.00")
        assert settlement.net_expected_amount == Decimal("1464.60")
        assert settlement.settled_amount == Decimal("1464.60")
        assert settlement.reference_number == "UTR0000001"
        for payment in payments:
            payment.refresh_from_db()
            assert payment.status == Collection.Status.SETTLED
            assert payment.deposit_id == settlement.pk
        assert not Discrepancy.objects.exists()
        assert actions_for(settlement) == [AuditAction.GATEWAY_SETTLEMENT_RECORDED]

    def test_short_settlement_raises_gateway_discrepancy(self, finance_user, upi_payments):
        payments = upi_payments("1000.00", "500.00")

        with pytest.raises(ValidationFailed, match="Remarks"):
            gateway_settle(
                finance_user,
                payments,
                gross_amount=Decimal("1490.00"),
                net_amount=Decimal("1454.60"),
            )
        settlement, _ = gateway_settle(
            finance_user,
            payments,
            gross_amount=Decimal("1490.00"),
            net_amount=Decimal("1454.60"),
            remarks="Gateway held back a disputed payment.",
        )

        assert settlement.status == BankDeposit.Status.SETTLED_WITH_MISMATCH
        discrepancy = Discrepancy.objects.get(deposit=settlement)
        assert discrepancy.kind == Discrepancy.Kind.GATEWAY_MISMATCH
        assert discrepancy.direction == Discrepancy.Direction.SHORT
        assert discrepancy.amount == Decimal("10.00")
        assert discrepancy.branch is None

    def test_report_must_add_up(self, finance_user, upi_payments):
        with pytest.raises(ValidationFailed, match="gross amount less fee and tax"):
            gateway_settle(finance_user, upi_payments("1500.00"), net_amount=Decimal("1470.00"))

    def test_up_to_date_settles_everything_captured_by_then(self, finance_user, upi_payments):
        three_days_ago = timezone.now() - timedelta(days=3)
        older = upi_payments("1000.00", "500.00", collected_at=three_days_ago)
        recent = upi_payments("900.00")

        settlement, _ = gateway_settle(finance_user, up_to_date=TODAY() - timedelta(days=1))

        assert settlement.expected_amount == Decimal("1500.00")
        assert set(settlement.collections.values_list("pk", flat=True)) == {c.pk for c in older}
        recent[0].refresh_from_db()
        assert recent[0].status == Collection.Status.COLLECTED

    def test_up_to_date_is_capped_at_one_batch(self, finance_user, upi_payments, monkeypatch):
        monkeypatch.setattr(services, "MAX_SETTLEMENT_ITEMS", 1)
        upi_payments("1000.00", "500.00")

        with pytest.raises(ValidationFailed) as exc:
            gateway_settle(finance_user, up_to_date=TODAY())

        assert exc.value.details["unsettled_count"] == 2
        assert not BankDeposit.objects.exists()

    def test_retry_with_same_key_replays_the_settlement(self, finance_user, upi_payments):
        payments = upi_payments("1000.00", "500.00")
        key = uuid.uuid4()
        settlement, _ = gateway_settle(finance_user, payments, idempotency_key=key)

        replayed, created = gateway_settle(finance_user, payments[::-1], idempotency_key=key)

        assert (replayed.pk, created) == (settlement.pk, False)

    @pytest.mark.parametrize(
        "change",
        [
            {"fee_amount": Decimal("20.00"), "tax_amount": Decimal("15.40")},
            {"collection_ids": None, "up_to_date": TODAY()},
        ],
    )
    def test_reusing_key_for_another_selection_or_split_conflicts(
        self, finance_user, upi_payments, change
    ):
        payments = upi_payments("1000.00", "500.00")
        key = uuid.uuid4()
        gateway_settle(finance_user, payments, idempotency_key=key)

        with pytest.raises(IdempotencyConflict):
            gateway_settle(finance_user, payments, idempotency_key=key, **change)

    def test_reusing_key_for_other_payments_conflicts(self, finance_user, upi_payments):
        first, second = upi_payments("1500.00"), upi_payments("1500.00")
        key = uuid.uuid4()
        gateway_settle(finance_user, first, idempotency_key=key)

        with pytest.raises(IdempotencyConflict):
            gateway_settle(finance_user, second, idempotency_key=key)
        second[0].refresh_from_db()
        assert second[0].status == Collection.Status.COLLECTED

    def test_up_to_date_with_nothing_to_settle(self, finance_user):
        with pytest.raises(ValidationFailed, match="no unsettled"):
            gateway_settle(finance_user, up_to_date=TODAY())

    def test_only_unsettled_upi_collections_qualify(self, finance_user, upi_payments, loan):
        cash = factories.CollectionFactory(loan=loan)
        payment = upi_payments("1500.00")[0]
        gateway_settle(finance_user, [payment])

        for ineligible in (cash, payment):
            with pytest.raises(ValidationFailed) as exc:
                gateway_settle(finance_user, [ineligible], utr="UTR-NEW")
            assert exc.value.details == {"collection_ids": [ineligible.pk]}
        with pytest.raises(ResourceNotFound):
            gateway_settle(finance_user, collection_ids=[999_999], utr="UTR-NEW")

    def test_duplicate_utr_is_rejected(self, finance_user, upi_payments):
        gateway_settle(finance_user, upi_payments("1500.00"))

        with pytest.raises(DuplicateBankReference):
            gateway_settle(finance_user, upi_payments("1500.00"), utr="utr 0000001")

    def test_cannot_settle_before_the_payments(self, finance_user, upi_payments):
        with pytest.raises(ValidationFailed, match="before the payments"):
            gateway_settle(
                finance_user, upi_payments("1500.00"), settled_on=TODAY() - timedelta(days=1)
            )

    def test_retry_returns_original_settlement(self, finance_user, upi_payments):
        payments = upi_payments("1500.00")
        key = uuid.uuid4()
        first, _ = gateway_settle(finance_user, payments, idempotency_key=key)

        replayed, created = gateway_settle(finance_user, payments, idempotency_key=key)

        assert not created
        assert replayed.pk == first.pk
        with pytest.raises(IdempotencyConflict):
            gateway_settle(finance_user, payments, idempotency_key=key, net_amount=Decimal("1.00"))

    def test_branch_manager_cannot_record_gateway_settlements(self, manager, upi_payments):
        with pytest.raises(ScopeViolation):
            gateway_settle(manager, upi_payments("1500.00"))


def test_gateway_settlement_needs_a_gateway_account(finance_user, upi_payments):
    with pytest.raises(ValidationFailed, match="gateway settlement account"):
        gateway_settle(finance_user, upi_payments("1500.00"))


# Delayed settlements ----------------------------------------------------------------------


class TestDelayedSettlements:
    @pytest.mark.parametrize(("age", "delayed"), [(0, False), (2, False), (3, True)])
    def test_pending_beyond_sla_is_delayed(self, settings, age, delayed):
        settings.SETTLEMENT_SLA_DAYS = 2
        deposit = factories.BankDepositFactory(deposit_date=TODAY() - timedelta(days=age))

        assert deposit.is_delayed is delayed
        assert deposit.days_pending == age
        assert BankDeposit.objects.delayed().filter(pk=deposit.pk).exists() is delayed

    def test_settled_deposits_are_never_delayed(self):
        deposit = factories.BankDepositFactory(
            deposit_date=TODAY() - timedelta(days=10), settled=True
        )

        assert not deposit.is_delayed
        assert deposit.days_pending is None

    def test_flagging_is_audited_once_per_day(self, caplog):
        delayed = factories.BankDepositFactory(deposit_date=TODAY() - timedelta(days=5))
        factories.BankDepositFactory(deposit_date=TODAY())
        factories.BankDepositFactory(deposit_date=TODAY() - timedelta(days=5), settled=True)

        assert services.flag_delayed_settlements() == [delayed]
        assert services.flag_delayed_settlements() == []

        entry = AuditLog.objects.get(action=AuditAction.DEPOSIT_SETTLEMENT_DELAYED)
        assert entry.entity_id == str(delayed.pk)
        assert entry.actor is None
        assert entry.after["days_pending"] == 5
        assert delayed.deposit_number in caplog.text

    def test_management_command(self, capsys):
        factories.BankDepositFactory(
            deposit_date=TODAY() - timedelta(days=4), deposited_amount=Decimal("2500.00")
        )

        call_command("flag_delayed_settlements")
        call_command("flag_delayed_settlements")

        output = capsys.readouterr().out.splitlines()
        assert output == [
            "Flagged 1 delayed settlement(s) worth 2500.00.",
            "Flagged 0 delayed settlement(s) worth 0.00.",
        ]


# Bank accounts --------------------------------------------------------------------------------


class TestBankAccounts:
    def test_create_is_audited(self, admin_user):
        account = services.create_bank_account(
            admin_user,
            bank_name="HDFC Bank",
            account_name="CashTrail Collections",
            account_number_last4="4321",
            ifsc="HDFC0000123",
        )

        assert actions_for(account) == [AuditAction.BANK_ACCOUNT_CREATED]

    def test_only_admins_manage_accounts(self, finance_user, bank_account):
        with pytest.raises(ScopeViolation):
            services.update_bank_account(finance_user, bank_account, is_active=False)

    def test_identity_is_frozen_once_deposits_reference_it(self, admin_user, bank_account):
        factories.BankDepositFactory(bank_account=bank_account)

        with pytest.raises(RecordLocked) as exc:
            services.update_bank_account(admin_user, bank_account, account_number_last4="9999")
        assert exc.value.details == {"fields": ["account_number_last4"]}

        account = services.update_bank_account(
            admin_user, bank_account, account_name="Renamed", is_active=False
        )
        assert (account.account_name, account.is_active) == ("Renamed", False)
        entry = AuditLog.objects.get(action=AuditAction.BANK_ACCOUNT_UPDATED)
        assert entry.before == {"account_name": bank_account.account_name, "is_active": True}

    def test_one_active_gateway_account(self, admin_user, gateway_bank_account):
        with pytest.raises(DomainError) as exc:
            services.create_bank_account(
                admin_user,
                bank_name="Razorpay",
                account_name="Second gateway",
                account_number_last4="0001",
                is_gateway=True,
            )
        assert exc.value.code == "GATEWAY_ACCOUNT_EXISTS"

        services.update_bank_account(admin_user, gateway_bank_account, is_active=False)
        assert BankAccount.objects.filter(is_gateway=True, is_active=True).count() == 0

    def test_gateway_account_cannot_be_reactivated_beside_another(
        self, admin_user, gateway_bank_account
    ):
        services.update_bank_account(admin_user, gateway_bank_account, is_active=False)
        replacement = factories.BankAccountFactory(gateway=True)

        with pytest.raises(DomainError) as exc:
            services.update_bank_account(admin_user, gateway_bank_account, is_active=True)

        assert exc.value.code == "GATEWAY_ACCOUNT_EXISTS"
        services.update_bank_account(admin_user, replacement, is_active=False)
        account = services.update_bank_account(admin_user, gateway_bank_account, is_active=True)
        assert account.is_active
