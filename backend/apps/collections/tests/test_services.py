import importlib
import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from django.apps import apps as django_apps
from django.db import DatabaseError, connection, transaction
from django.utils import timezone

from apps.audit.models import AuditAction, AuditLog
from apps.collections.models import Allocation, Collection
from apps.collections.services import (
    record_collection,
    record_gateway_payment,
    void_collection,
)
from apps.core.dates import business_date
from apps.core.exceptions import (
    IdempotencyConflict,
    InvalidStateTransition,
    OverCollection,
    PossibleDuplicate,
    ScopeViolation,
    ValidationFailed,
)
from apps.core.testing import factories
from apps.customers.services import update_customer
from apps.loans.models import Installment, Loan

pytestmark = pytest.mark.django_db

EMI = Decimal("8885.00")
TOTAL_PAYABLE = Decimal("106619.00")


def installments(loan):
    return list(loan.installments.order_by("installment_no"))


def cash(actor, loan, amount, **kwargs):
    kwargs.setdefault("idempotency_key", uuid.uuid4())
    return record_collection(
        actor=actor, loan=loan, amount=Decimal(amount), mode=Collection.Mode.CASH, **kwargs
    )


class TestAllocation:
    def test_partial_payment_leaves_installment_partially_paid(self, agent, loan):
        collection, replayed = cash(agent, loan, "5000.00")

        assert replayed is False
        assert collection.status == Collection.Status.COLLECTED
        assert collection.branch_id == loan.branch_id
        assert collection.customer_id == loan.customer_id
        first, second, *_ = installments(loan)
        assert (first.amount_paid, first.status) == (Decimal("5000.00"), "PARTIALLY_PAID")
        assert first.paid_at is None
        assert second.status == Installment.Status.PENDING
        loan.refresh_from_db()
        assert loan.amount_paid == Decimal("5000.00")
        assert loan.outstanding == TOTAL_PAYABLE - Decimal("5000.00")
        assert list(collection.allocations.values_list("installment_id", "amount")) == [
            (first.pk, Decimal("5000.00"))
        ]

    def test_advance_payment_spreads_over_installments_oldest_first(self, agent, loan):
        collection, _ = cash(agent, loan, "20000.00")

        first, second, third, fourth, *_ = installments(loan)
        assert [first.status, second.status, third.status, fourth.status] == [
            "PAID",
            "PAID",
            "PARTIALLY_PAID",
            "PENDING",
        ]
        assert third.amount_paid == Decimal("20000.00") - 2 * EMI
        assert first.paid_at == collection.collected_at
        amounts = collection.allocations.order_by("installment__installment_no")
        assert [a.amount for a in amounts] == [EMI, EMI, Decimal("2230.00")]

    def test_second_payment_completes_the_partly_paid_installment(self, agent, loan, collect):
        collect(agent, loan, "5000.00")
        second_payment, _ = cash(agent, loan, "3885.00")

        first = installments(loan)[0]
        assert first.status == Installment.Status.PAID
        assert first.allocations.count() == 2
        assert second_payment.allocations.get().amount == Decimal("3885.00")

    def test_exact_payoff_closes_the_loan(self, agent, loan):
        cash(agent, loan, str(TOTAL_PAYABLE))

        loan.refresh_from_db()
        assert loan.status == Loan.Status.CLOSED
        assert loan.closed_at is not None
        assert loan.outstanding == 0
        assert not loan.installments.exclude(status=Installment.Status.PAID).exists()
        assert AuditLog.objects.filter(
            action=AuditAction.LOAN_CLOSED, entity_type="loan", entity_id=str(loan.pk)
        ).exists()

    def test_records_an_audit_entry_with_allocations(self, agent, loan):
        collection, _ = cash(agent, loan, "9000.00")

        entry = AuditLog.objects.get(action=AuditAction.COLLECTION_RECORDED)
        assert entry.actor == agent
        assert entry.entity_id == str(collection.pk)
        assert entry.branch_id == loan.branch_id
        assert entry.after["amount"] == "9000.00"
        assert entry.after["receipt_number"] == collection.receipt_number
        assert [a["amount"] for a in entry.after["allocations"]] == ["8885.00", "115.00"]


class TestOverCollection:
    def test_amount_above_outstanding_is_refused(self, agent, loan):
        with pytest.raises(OverCollection) as exc:
            cash(agent, loan, str(TOTAL_PAYABLE + Decimal("0.01")))

        assert exc.value.details["outstanding"] == str(TOTAL_PAYABLE)
        assert not Collection.objects.exists()

    def test_outstanding_reflects_earlier_payments(self, agent, loan, collect):
        collect(agent, loan, "100000.00")

        with pytest.raises(OverCollection) as exc:
            cash(agent, loan, "7000.00")
        assert exc.value.details["outstanding"] == "6619.00"


class TestIdempotency:
    def test_same_key_and_payload_replays_the_original(self, agent, loan):
        key = uuid.uuid4()
        original, _ = cash(agent, loan, "5000.00", idempotency_key=key)
        replay, replayed = cash(agent, loan, "5000.00", idempotency_key=key)

        assert replayed is True
        assert replay.pk == original.pk
        assert Collection.objects.count() == 1
        assert AuditLog.objects.filter(action=AuditAction.COLLECTION_RECORDED).count() == 1
        loan.refresh_from_db()
        assert loan.amount_paid == Decimal("5000.00")

    def test_same_key_with_a_different_amount_conflicts(self, agent, loan):
        key = uuid.uuid4()
        original, _ = cash(agent, loan, "5000.00", idempotency_key=key)

        with pytest.raises(IdempotencyConflict) as exc:
            cash(agent, loan, "5001.00", idempotency_key=key)
        assert exc.value.details == {"receipt_number": original.receipt_number}

    def test_same_key_on_another_loan_conflicts(self, agent, loan, customer):
        key = uuid.uuid4()
        cash(agent, loan, "5000.00", idempotency_key=key)

        with pytest.raises(IdempotencyConflict):
            cash(agent, factories.LoanFactory(customer=customer), "5000.00", idempotency_key=key)

    def test_replay_still_works_after_the_payment_closed_the_loan(self, agent, loan):
        key = uuid.uuid4()
        original, _ = cash(agent, loan, str(TOTAL_PAYABLE), idempotency_key=key)

        replay, replayed = cash(agent, loan, str(TOTAL_PAYABLE), idempotency_key=key)
        assert (replay.pk, replayed) == (original.pk, True)

    def test_keys_are_scoped_per_agent(self, agent, other_agent, loan, other_agent_loan):
        key = uuid.uuid4()
        cash(agent, loan, "5000.00", idempotency_key=key)

        _, replayed = cash(other_agent, other_agent_loan, "5000.00", idempotency_key=key)
        assert replayed is False


class TestPossibleDuplicate:
    def test_same_amount_on_same_loan_within_window_needs_confirmation(self, agent, loan):
        first, _ = cash(agent, loan, "5000.00")

        with pytest.raises(PossibleDuplicate) as exc:
            cash(agent, loan, "5000.00")
        assert exc.value.details["receipt_number"] == first.receipt_number
        assert exc.value.details["collection_id"] == first.pk

        second, replayed = cash(agent, loan, "5000.00", confirm_duplicate=True)
        assert replayed is False
        assert second.pk != first.pk

    def test_different_amount_is_not_a_duplicate(self, agent, loan):
        cash(agent, loan, "5000.00")
        cash(agent, loan, "5000.50")

        assert Collection.objects.count() == 2

    def test_entries_outside_the_window_are_not_duplicates(self, agent, loan, settings):
        first, _ = cash(agent, loan, "5000.00")
        Collection.objects.filter(pk=first.pk).update(
            collected_at=timezone.now() - timedelta(minutes=settings.DUPLICATE_WINDOW_MINUTES + 1)
        )

        cash(agent, loan, "5000.00")
        assert Collection.objects.count() == 2

    def test_voided_entries_are_not_duplicates(self, agent, loan):
        first, _ = cash(agent, loan, "5000.00")
        void_collection(actor=agent, collection=first, reason="Wrong customer.")

        cash(agent, loan, "5000.00")
        assert Collection.objects.exclude(status=Collection.Status.VOIDED).count() == 1


class TestEligibility:
    def test_agent_not_assigned_to_the_customer_is_refused(self, other_agent, loan):
        with pytest.raises(ScopeViolation):
            cash(other_agent, loan, "5000.00")

    def test_non_agents_cannot_record_repayments(self, manager, loan):
        with pytest.raises(ScopeViolation):
            cash(manager, loan, "5000.00")

    def test_inactive_customer_is_refused(self, agent, loan, customer):
        customer.is_active = False
        customer.save(update_fields=["is_active"])

        with pytest.raises(ValidationFailed) as exc:
            cash(agent, loan, "5000.00")
        assert exc.value.code == "CUSTOMER_INACTIVE"

    def test_closed_loan_is_refused(self, agent, loan, collect):
        collect(agent, loan, str(TOTAL_PAYABLE))

        with pytest.raises(ValidationFailed) as exc:
            cash(agent, loan, "1.00")
        assert exc.value.code == "LOAN_NOT_ACTIVE"

    @pytest.mark.parametrize("amount", ["0", "-10.00", "10.005", "abc"])
    def test_invalid_amounts_are_refused(self, agent, loan, amount):
        with pytest.raises(ValidationFailed):
            record_collection(
                actor=agent,
                loan=loan,
                amount=amount,
                mode=Collection.Mode.CASH,
                idempotency_key=uuid.uuid4(),
            )

    def test_float_amounts_are_refused(self, agent, loan):
        with pytest.raises(ValidationFailed):
            record_collection(
                actor=agent,
                loan=loan,
                amount=100.5,
                mode=Collection.Mode.CASH,
                idempotency_key=uuid.uuid4(),
            )

    def test_future_dated_collection_is_refused(self, agent, loan):
        with pytest.raises(ValidationFailed):
            cash(agent, loan, "100.00", collected_at=timezone.now() + timedelta(hours=1))

    @pytest.mark.parametrize(
        ("mode", "key", "gateway_payment_id"),
        [
            (Collection.Mode.CASH, None, None),
            (Collection.Mode.CASH, uuid.uuid4(), "pay_123"),
            (Collection.Mode.UPI, None, None),
            ("CHEQUE", uuid.uuid4(), None),
        ],
    )
    def test_mode_requirements(self, agent, loan, mode, key, gateway_payment_id):
        with pytest.raises(ValidationFailed):
            record_collection(
                actor=agent,
                loan=loan,
                amount=Decimal("100.00"),
                mode=mode,
                idempotency_key=key,
                gateway_payment_id=gateway_payment_id,
            )


class TestUpi:
    def upi(self, agent, loan, amount, payment_id, **kwargs):
        return record_collection(
            actor=agent,
            loan=loan,
            amount=Decimal(amount),
            mode=Collection.Mode.UPI,
            idempotency_key=None,
            gateway_payment_id=payment_id,
            **kwargs,
        )

    def test_records_a_gateway_payment(self, agent, loan):
        collection, replayed = self.upi(agent, loan, "5000.00", "pay_ABC123")

        assert replayed is False
        assert collection.mode == Collection.Mode.UPI
        assert collection.gateway_payment_id == "pay_ABC123"
        assert collection.allocations.count() == 1

    def test_same_gateway_payment_is_recorded_once(self, agent, loan):
        original, _ = self.upi(agent, loan, "5000.00", "pay_ABC123")
        replay, replayed = self.upi(agent, loan, "5000.00", "pay_ABC123")

        assert (replay.pk, replayed) == (original.pk, True)
        assert Collection.objects.count() == 1

    def test_same_gateway_payment_with_different_amount_conflicts(self, agent, loan):
        self.upi(agent, loan, "5000.00", "pay_ABC123")

        with pytest.raises(IdempotencyConflict):
            self.upi(agent, loan, "4000.00", "pay_ABC123")

    def test_distinct_gateway_payments_are_never_treated_as_duplicates(self, agent, loan):
        self.upi(agent, loan, "5000.00", "pay_ONE")
        self.upi(agent, loan, "5000.00", "pay_TWO")

        assert Collection.objects.count() == 2


class TestBalanceAfter:
    def test_each_receipt_keeps_the_balance_it_left(self, agent, loan, collect):
        first = collect(agent, loan, "5000.00")
        second = collect(agent, loan, "3000.00")

        first.refresh_from_db()
        assert first.balance_after == TOTAL_PAYABLE - Decimal("5000.00")
        assert second.balance_after == TOTAL_PAYABLE - Decimal("8000.00")

    def test_a_void_does_not_rewrite_any_receipt(self, agent, loan, collect):
        first = collect(agent, loan, "5000.00")
        second = collect(agent, loan, "3000.00")

        void_collection(actor=agent, collection=first, reason="Wrong amount.")
        third = collect(agent, loan, "1000.00")

        first.refresh_from_db()
        second.refresh_from_db()
        assert first.balance_after == TOTAL_PAYABLE - Decimal("5000.00")
        assert second.balance_after == TOTAL_PAYABLE - Decimal("8000.00")
        # Recorded after the void, so only the 3,000 receipt counts before it.
        assert third.balance_after == TOTAL_PAYABLE - Decimal("4000.00")

    def test_payoff_receipt_shows_zero(self, agent, loan):
        collection, _ = cash(agent, loan, str(TOTAL_PAYABLE))

        assert collection.balance_after == Decimal("0.00")

    def test_gateway_payment_records_the_balance(self, agent, loan):
        collection, _ = record_gateway_payment(
            agent=agent, loan=loan, amount=Decimal("2500.00"), gateway_payment_id="pay_BAL"
        )

        assert collection.balance_after == TOTAL_PAYABLE - Decimal("2500.00")


class TestBalanceAfterBackfill:
    @staticmethod
    def rewrite_balances(**values):
        """Stand in for rows recorded before the column existed; the guard trigger forbids
        rewriting an issued balance, so triggers are paused for this one update."""
        where = values.pop("where", {})
        with connection.cursor() as cursor:
            cursor.execute("SET session_replication_role = replica")
        try:
            Collection.objects.filter(**where).update(**values)
        finally:
            with connection.cursor() as cursor:
                cursor.execute("SET session_replication_role = origin")

    @staticmethod
    def backfill():
        migration = importlib.import_module("apps.collections.migrations.0003_balance_after")
        migration.backfill_balance_after(django_apps, None)

    def test_rebuilds_the_balances_receipts_recorded(self, agent, loan, collect):
        first = collect(agent, loan, "5000.00")
        second = collect(agent, loan, "3000.00")
        void_collection(actor=agent, collection=second, reason="Entered twice.")
        third = collect(agent, loan, "1000.00")
        recorded = {c.pk: c.balance_after for c in Collection.objects.all()}
        self.rewrite_balances(balance_after=None)

        self.backfill()

        assert {c.pk: c.balance_after for c in Collection.objects.all()} == recorded
        assert recorded[first.pk] == TOTAL_PAYABLE - Decimal("5000.00")
        assert recorded[second.pk] == TOTAL_PAYABLE - Decimal("8000.00")
        assert recorded[third.pk] == TOTAL_PAYABLE - Decimal("6000.00")

    def test_leaves_recorded_balances_alone(self, agent, loan, collect):
        collection = collect(agent, loan, "5000.00")
        self.rewrite_balances(where={"pk": collection.pk}, balance_after=Decimal("1.00"))

        self.backfill()

        collection.refresh_from_db()
        assert collection.balance_after == Decimal("1.00")


class TestReceiptNumbers:
    def test_numbers_are_sequential_per_branch_and_day(
        self, agent, loan, other_branch_agent, other_branch_loan, collect
    ):
        today = business_date().strftime("%Y%m%d")
        first = collect(agent, loan, "100.00")
        second = collect(agent, loan, "200.00")
        elsewhere = collect(other_branch_agent, other_branch_loan, "100.00")

        assert first.receipt_number == f"RCT-BLR01-{today}-00001"
        assert second.receipt_number == f"RCT-BLR01-{today}-00002"
        assert elsewhere.receipt_number == f"RCT-MUM01-{today}-00001"

    def test_number_uses_the_business_date_of_collection(self, agent, loan, collect):
        yesterday = timezone.now() - timedelta(days=1)

        collection = collect(agent, loan, "100.00", collected_at=yesterday)
        assert collection.receipt_number.startswith(f"RCT-BLR01-{business_date(yesterday):%Y%m%d}-")

    def test_refused_requests_do_not_consume_numbers(self, agent, loan, collect):
        with pytest.raises(OverCollection):
            cash(agent, loan, "999999.00")

        assert collect(agent, loan, "100.00").receipt_number.endswith("-00001")


class TestVoid:
    def test_void_reverses_allocations_and_balances(self, agent, loan):
        collection, _ = cash(agent, loan, "10000.00")

        voided = void_collection(actor=agent, collection=collection, reason="Entered twice.")

        assert voided.status == Collection.Status.VOIDED
        assert voided.voided_by == agent
        assert voided.void_reason == "Entered twice."
        assert voided.voided_at is not None
        assert not collection.allocations.filter(reversed_at__isnull=True).exists()
        assert Allocation.objects.filter(collection=collection).count() == 2
        assert all(i.amount_paid == 0 and i.status == "PENDING" for i in installments(loan))
        loan.refresh_from_db()
        assert loan.amount_paid == 0
        entry = AuditLog.objects.get(action=AuditAction.COLLECTION_VOIDED)
        assert (entry.before["status"], entry.after["status"]) == ("COLLECTED", "VOIDED")

    def test_void_moves_later_payments_into_the_freed_installments(self, agent, loan, collect):
        first = collect(agent, loan, "5000.00")
        second = collect(agent, loan, "6000.00")  # 3885.00 on EMI 1, 2115.00 on EMI 2

        void_collection(actor=agent, collection=first, reason="Wrong amount.")

        one, two = installments(loan)[:2]
        assert (one.amount_paid, one.status) == (Decimal("6000.00"), "PARTIALLY_PAID")
        assert (two.amount_paid, two.status) == (Decimal("0.00"), "PENDING")
        effective = second.allocations.filter(reversed_at__isnull=True)
        assert list(effective.values_list("installment", "amount")) == [
            (one.pk, Decimal("6000.00"))
        ]
        assert second.allocations.filter(reversed_at__isnull=False).count() == 2
        loan.refresh_from_db()
        assert loan.amount_paid == Decimal("6000.00")

    def test_void_of_a_partial_payment_lets_a_later_one_cover_the_installment(
        self, agent, loan, collect
    ):
        first = collect(agent, loan, "600.00")
        collect(agent, loan, "8885.00")  # 8285.00 completes EMI 1, 600 starts EMI 2

        void_collection(actor=agent, collection=first, reason="Wrong customer.")

        one, two = installments(loan)[:2]
        assert (one.amount_paid, one.status) == (Decimal("8885.00"), "PAID")
        assert one.paid_at is not None
        assert (two.amount_paid, two.status) == (Decimal("0.00"), "PENDING")

    def test_void_leaves_earlier_receipts_untouched(self, agent, loan, collect):
        first = collect(agent, loan, "5000.00")
        second = collect(agent, loan, "6000.00")
        allocations = list(first.allocations.values_list("pk", flat=True))

        void_collection(actor=agent, collection=second, reason="Entered twice.")

        kept = first.allocations.filter(reversed_at__isnull=True).values_list("pk", flat=True)
        assert list(kept) == allocations
        one, two = installments(loan)[:2]
        assert (one.amount_paid, two.amount_paid) == (Decimal("5000.00"), Decimal("0.00"))

    def test_void_is_refused_once_the_customer_is_inactive(self, agent, manager, loan, collect):
        receipt = collect(agent, loan, str(loan.total_payable))
        update_customer(manager, loan.customer, is_active=False)

        with pytest.raises(ValidationFailed) as error:
            void_collection(actor=agent, collection=receipt, reason="Mistake.")

        assert error.value.code == "CUSTOMER_INACTIVE"
        loan.refresh_from_db()
        assert loan.status == Loan.Status.CLOSED

    def test_void_reopens_a_loan_it_closed(self, agent, loan, collect):
        payoff = collect(agent, loan, str(TOTAL_PAYABLE))

        void_collection(actor=agent, collection=payoff, reason="Cheque bounced.")

        loan.refresh_from_db()
        assert loan.status == Loan.Status.ACTIVE
        assert loan.closed_at is None
        assert AuditLog.objects.filter(action=AuditAction.LOAN_REOPENED).exists()

    def test_reason_is_required(self, agent, loan, collect):
        collection = collect(agent, loan, "100.00")

        with pytest.raises(ValidationFailed):
            void_collection(actor=agent, collection=collection, reason="   ")

    def test_only_the_collecting_agent_can_void(self, agent, other_agent, loan, collect):
        collection = collect(agent, loan, "100.00")

        with pytest.raises(ScopeViolation):
            void_collection(actor=other_agent, collection=collection, reason="Mistake.")

    def test_submitted_cash_cannot_be_voided(self, agent, loan):
        submission = factories.CashSubmissionFactory(agent=agent)
        collection = factories.CollectionFactory(
            loan=loan, status=Collection.Status.SUBMITTED, submission=submission
        )

        with pytest.raises(InvalidStateTransition):
            void_collection(actor=agent, collection=collection, reason="Mistake.")

    def test_cannot_void_twice(self, agent, loan, collect):
        collection = collect(agent, loan, "100.00")
        void_collection(actor=agent, collection=collection, reason="Mistake.")

        with pytest.raises(InvalidStateTransition):
            void_collection(actor=agent, collection=collection, reason="Again.")

    def test_upi_collections_cannot_be_voided(self, agent, loan):
        collection, _ = record_collection(
            actor=agent,
            loan=loan,
            amount=Decimal("100.00"),
            mode=Collection.Mode.UPI,
            idempotency_key=None,
            gateway_payment_id="pay_VOID",
        )

        with pytest.raises(InvalidStateTransition):
            void_collection(actor=agent, collection=collection, reason="Mistake.")

    def test_reversed_allocations_cannot_be_rewritten(self, agent, loan, collect):
        collection = collect(agent, loan, "100.00")
        void_collection(actor=agent, collection=collection, reason="Mistake.")
        allocation = collection.allocations.get()

        with transaction.atomic(), pytest.raises(DatabaseError, match="RECORD_LOCKED"):
            Allocation.objects.filter(pk=allocation.pk).update(amount=Decimal("1.00"))
