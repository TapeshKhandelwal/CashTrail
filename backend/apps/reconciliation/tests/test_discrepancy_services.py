from decimal import Decimal

import pytest
from django.db import DatabaseError, transaction

from apps.audit.models import AuditAction, AuditLog
from apps.core.exceptions import (
    InvalidStateTransition,
    ResourceNotFound,
    ScopeViolation,
    ValidationFailed,
)
from apps.core.testing import factories
from apps.reconciliation import services
from apps.reconciliation.models import Discrepancy

pytestmark = pytest.mark.django_db

Kind = Discrepancy.Kind
Reason = Discrepancy.ReasonCode


@pytest.fixture
def approved_submission(manager, pending_submission):
    return services.approve_submission(
        manager, pending_submission, received_amount=Decimal("50000.00")
    )


@pytest.fixture
def cash_deposit(branch, manager):
    return factories.BankDepositFactory(branch=branch, created_by=manager)


@pytest.fixture
def gateway_deposit(gateway_bank_account):
    return factories.BankDepositFactory(gateway=True)


@pytest.fixture
def shortage(manager, pending_submission):
    submission = services.approve_submission(
        manager,
        pending_submission,
        received_amount=Decimal("48500.00"),
        reason_code=Reason.AGENT_SHORTAGE,
        remarks="Short by 1500.",
    )
    return submission.discrepancies.get()


@pytest.fixture
def deposit_mismatch(cash_deposit, finance_user):
    return services.raise_discrepancy(
        finance_user,
        kind=Kind.DEPOSIT_MISMATCH,
        direction=Discrepancy.Direction.SHORT,
        amount=Decimal("200.00"),
        reason_code=Reason.BANK_CHARGES,
        notes="Cash deposit fee deducted at the counter.",
        deposit_id=cash_deposit.pk,
    )


class TestRaiseDiscrepancy:
    def test_manager_records_cash_shortage_found_later(
        self, manager, agent, branch, approved_submission
    ):
        discrepancy = services.raise_discrepancy(
            manager,
            kind=Kind.CASH_SHORTAGE,
            amount=Decimal("500.00"),
            reason_code=Reason.OTHER,
            notes=" Counterfeit ₹500 note found while bundling. ",
            submission_id=approved_submission.pk,
        )

        assert discrepancy.direction == Discrepancy.Direction.SHORT
        assert discrepancy.agent == agent
        assert discrepancy.branch == branch
        assert discrepancy.raised_by == manager
        assert discrepancy.notes == "Counterfeit ₹500 note found while bundling."
        assert AuditLog.objects.filter(
            action=AuditAction.DISCREPANCY_RAISED, entity_id=str(discrepancy.pk)
        ).exists()

    def test_cash_kind_direction_must_match(self, manager, approved_submission):
        with pytest.raises(ValidationFailed):
            services.raise_discrepancy(
                manager,
                kind=Kind.CASH_EXCESS,
                direction=Discrepancy.Direction.SHORT,
                amount=Decimal("10.00"),
                reason_code=Reason.OTHER,
                notes="Mismatch.",
                submission_id=approved_submission.pk,
            )

    def test_cash_discrepancy_needs_an_approved_submission(self, manager, pending_submission):
        with pytest.raises(ValidationFailed) as excinfo:
            services.raise_discrepancy(
                manager,
                kind=Kind.CASH_SHORTAGE,
                amount=Decimal("10.00"),
                reason_code=Reason.OTHER,
                notes="Too early.",
                submission_id=pending_submission.pk,
            )

        assert excinfo.value.details == {"status": "SUBMITTED"}

    def test_cash_discrepancy_needs_a_submission(self, manager, cash_deposit):
        with pytest.raises(ValidationFailed):
            services.raise_discrepancy(
                manager,
                kind=Kind.CASH_SHORTAGE,
                amount=Decimal("10.00"),
                reason_code=Reason.OTHER,
                notes="Wrong source.",
                deposit_id=cash_deposit.pk,
            )

    def test_other_branch_submission_is_not_found(self, other_branch_manager, approved_submission):
        with pytest.raises(ResourceNotFound):
            services.raise_discrepancy(
                other_branch_manager,
                kind=Kind.CASH_SHORTAGE,
                amount=Decimal("10.00"),
                reason_code=Reason.OTHER,
                notes="Not mine.",
                submission_id=approved_submission.pk,
            )

    def test_finance_records_deposit_mismatch(self, deposit_mismatch, cash_deposit, branch):
        assert deposit_mismatch.deposit == cash_deposit
        assert deposit_mismatch.branch == branch
        assert deposit_mismatch.agent is None
        assert deposit_mismatch.direction == Discrepancy.Direction.SHORT

    def test_deposit_discrepancy_needs_a_direction(self, finance_user, cash_deposit):
        with pytest.raises(ValidationFailed) as excinfo:
            services.raise_discrepancy(
                finance_user,
                kind=Kind.SETTLEMENT_MISMATCH,
                amount=Decimal("10.00"),
                reason_code=Reason.BANK_ERROR,
                notes="Bank credited less.",
                deposit_id=cash_deposit.pk,
            )

        assert "direction" in excinfo.value.details

    def test_gateway_mismatch_applies_only_to_gateway_settlements(
        self, finance_user, cash_deposit, gateway_deposit
    ):
        with pytest.raises(ValidationFailed):
            services.raise_discrepancy(
                finance_user,
                kind=Kind.GATEWAY_MISMATCH,
                direction=Discrepancy.Direction.SHORT,
                amount=Decimal("10.00"),
                reason_code=Reason.OTHER,
                notes="Fee higher than agreed.",
                deposit_id=cash_deposit.pk,
            )

        discrepancy = services.raise_discrepancy(
            finance_user,
            kind=Kind.GATEWAY_MISMATCH,
            direction=Discrepancy.Direction.SHORT,
            amount=Decimal("10.00"),
            reason_code=Reason.OTHER,
            notes="Fee higher than agreed.",
            deposit_id=gateway_deposit.pk,
        )
        assert discrepancy.branch is None

    def test_failed_deposit_cannot_carry_a_discrepancy(self, finance_user, branch):
        deposit = factories.BankDepositFactory(branch=branch, failed=True)

        with pytest.raises(ValidationFailed):
            services.raise_discrepancy(
                finance_user,
                kind=Kind.SETTLEMENT_MISMATCH,
                direction=Discrepancy.Direction.SHORT,
                amount=Decimal("10.00"),
                reason_code=Reason.BANK_ERROR,
                notes="n/a",
                deposit_id=deposit.pk,
            )

    @pytest.mark.parametrize(
        ("actor", "kind"),
        [
            ("agent", Kind.CASH_SHORTAGE),
            ("finance_user", Kind.CASH_SHORTAGE),
            ("manager", Kind.SETTLEMENT_MISMATCH),
            ("manager", Kind.GATEWAY_MISMATCH),
        ],
    )
    def test_role_may_raise_only_its_kinds(self, request, actor, kind):
        with pytest.raises(ScopeViolation):
            services.raise_discrepancy(
                request.getfixturevalue(actor),
                kind=kind,
                direction=Discrepancy.Direction.SHORT,
                amount=Decimal("10.00"),
                reason_code=Reason.OTHER,
                notes="Not allowed.",
                submission_id=1,
            )

    def test_notes_are_required(self, manager, approved_submission):
        with pytest.raises(ValidationFailed):
            services.raise_discrepancy(
                manager,
                kind=Kind.CASH_SHORTAGE,
                amount=Decimal("10.00"),
                reason_code=Reason.OTHER,
                notes="  ",
                submission_id=approved_submission.pk,
            )


class TestResolveDiscrepancy:
    def test_manager_resolves_cash_shortage(self, manager, shortage):
        discrepancy = services.resolve_discrepancy(
            manager,
            shortage,
            outcome=Discrepancy.Status.RESOLVED,
            resolution_notes=" Agent repaid ₹1,500 in cash. ",
        )

        assert discrepancy.status == Discrepancy.Status.RESOLVED
        assert discrepancy.resolution_notes == "Agent repaid ₹1,500 in cash."
        assert discrepancy.resolved_by == manager
        assert discrepancy.resolved_at is not None
        entry = AuditLog.objects.get(
            action=AuditAction.DISCREPANCY_RESOLVED, entity_id=str(discrepancy.pk)
        )
        assert entry.before["status"] == Discrepancy.Status.OPEN
        assert entry.after["status"] == Discrepancy.Status.RESOLVED

    def test_admin_writes_off_cash_shortage(self, admin_user, shortage):
        discrepancy = services.resolve_discrepancy(
            admin_user,
            shortage,
            outcome=Discrepancy.Status.WRITTEN_OFF,
            resolution_notes="Below recovery threshold.",
        )

        assert discrepancy.status == Discrepancy.Status.WRITTEN_OFF
        assert AuditLog.objects.filter(
            action=AuditAction.DISCREPANCY_WRITTEN_OFF, entity_id=str(discrepancy.pk)
        ).exists()

    def test_finance_resolves_deposit_mismatch(self, finance_user, deposit_mismatch):
        discrepancy = services.resolve_discrepancy(
            finance_user,
            deposit_mismatch,
            outcome=Discrepancy.Status.WRITTEN_OFF,
            resolution_notes="Bank charge booked as expense.",
        )

        assert discrepancy.status == Discrepancy.Status.WRITTEN_OFF

    @pytest.mark.parametrize("actor", ["finance_user", "other_branch_manager", "agent"])
    def test_cash_discrepancy_belongs_to_branch_manager(self, request, shortage, actor):
        with pytest.raises(ScopeViolation):
            services.resolve_discrepancy(
                request.getfixturevalue(actor),
                shortage,
                outcome=Discrepancy.Status.RESOLVED,
                resolution_notes="Done.",
            )

    def test_deposit_discrepancy_belongs_to_finance(self, manager, deposit_mismatch):
        with pytest.raises(ScopeViolation):
            services.resolve_discrepancy(
                manager,
                deposit_mismatch,
                outcome=Discrepancy.Status.RESOLVED,
                resolution_notes="Done.",
            )

    def test_resolution_notes_are_required(self, manager, shortage):
        with pytest.raises(ValidationFailed):
            services.resolve_discrepancy(
                manager, shortage, outcome=Discrepancy.Status.RESOLVED, resolution_notes=" "
            )

    def test_cannot_reopen_by_resolving_to_open(self, manager, shortage):
        with pytest.raises(ValidationFailed):
            services.resolve_discrepancy(
                manager, shortage, outcome=Discrepancy.Status.OPEN, resolution_notes="Reopen."
            )

    def test_cannot_resolve_twice(self, manager, shortage):
        services.resolve_discrepancy(
            manager, shortage, outcome=Discrepancy.Status.RESOLVED, resolution_notes="Repaid."
        )

        with pytest.raises(InvalidStateTransition):
            services.resolve_discrepancy(
                manager,
                shortage,
                outcome=Discrepancy.Status.WRITTEN_OFF,
                resolution_notes="Again.",
            )

    def test_resolved_discrepancy_is_frozen_in_the_database(self, manager, shortage):
        services.resolve_discrepancy(
            manager, shortage, outcome=Discrepancy.Status.RESOLVED, resolution_notes="Repaid."
        )

        with (
            pytest.raises(DatabaseError, match="RECORD_LOCKED"),
            transaction.atomic(),
        ):
            Discrepancy.objects.filter(pk=shortage.pk).update(amount=Decimal("1.00"))
