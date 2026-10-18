import uuid
from decimal import Decimal

import pytest
from django.db import DatabaseError, transaction

from apps.audit.models import AuditAction, AuditLog
from apps.collections.models import Collection
from apps.core.exceptions import (
    IdempotencyConflict,
    InvalidStateTransition,
    ResourceNotFound,
    ScopeViolation,
    ValidationFailed,
)
from apps.reconciliation import selectors, services
from apps.reconciliation.exceptions import (
    DenominationMismatch,
    PendingSubmissionExists,
    SegregationOfDuties,
)
from apps.reconciliation.models import CashSubmission, Discrepancy

pytestmark = pytest.mark.django_db

Status = CashSubmission.Status


def _audit(action, entity):
    return AuditLog.objects.get(
        action=action, entity_type=entity._meta.model_name, entity_id=str(entity.pk)
    )


class TestCreateSubmission:
    def test_hands_receipts_over_with_server_computed_total(self, agent, branch, receive_cash):
        collections = receive_cash("30000.00", "20000.00")

        submission, created = services.create_submission(
            agent,
            collection_ids=[c.pk for c in collections],
            declared_amount=Decimal("50000.00"),
            idempotency_key=uuid.uuid4(),
        )

        assert created
        assert submission.status == Status.SUBMITTED
        assert submission.expected_amount == Decimal("50000.00")
        assert submission.branch == branch
        assert submission.submission_number.startswith("SUB-BLR01-")
        for collection in collections:
            collection.refresh_from_db()
            assert collection.status == Collection.Status.SUBMITTED
            assert collection.submission == submission
            assert collection.submitted_at == submission.submitted_at
        entry = _audit(AuditAction.SUBMISSION_CREATED, submission)
        assert entry.actor == agent
        assert entry.after["expected_amount"] == "50000.00"
        assert entry.after["collection_ids"] == sorted(c.pk for c in collections)

    def test_declared_amount_may_differ_from_expected(self, receive_cash, submit):
        submission = submit(receive_cash("1000.00"), declared="900.00")

        assert submission.expected_amount == Decimal("1000.00")
        assert submission.declared_amount == Decimal("900.00")

    def test_stores_normalized_denominations(self, receive_cash, submit):
        submission = submit(receive_cash("1200.00"), denominations={"100": 2, "500": 2, "10": 0})

        assert submission.denominations == {"500": 2, "100": 2}

    def test_denominations_must_add_up_to_declared_amount(self, agent, receive_cash):
        collection = receive_cash("1200.00")[0]

        with pytest.raises(DenominationMismatch) as excinfo:
            services.create_submission(
                agent,
                collection_ids=[collection.pk],
                declared_amount=Decimal("1200.00"),
                denominations={"500": 2},
                idempotency_key=uuid.uuid4(),
            )

        assert excinfo.value.status_code == 422
        assert excinfo.value.details == {
            "denominations_total": "1000.00",
            "declared_amount": "1200.00",
        }

    def test_replay_with_same_key_returns_original(self, agent, receive_cash):
        collections = receive_cash("1000.00", "500.00")
        key = uuid.uuid4()
        payload = {
            "collection_ids": [c.pk for c in collections],
            "declared_amount": Decimal("1500.00"),
            "idempotency_key": key,
        }
        first, _ = services.create_submission(agent, **payload)

        replay, created = services.create_submission(
            agent, **{**payload, "collection_ids": payload["collection_ids"][::-1]}
        )

        assert not created
        assert replay == first
        assert CashSubmission.objects.count() == 1

    def test_same_key_with_different_payload_conflicts(self, agent, receive_cash):
        collections = receive_cash("1000.00")
        key = uuid.uuid4()
        services.create_submission(
            agent,
            collection_ids=[collections[0].pk],
            declared_amount=Decimal("1000.00"),
            idempotency_key=key,
        )

        with pytest.raises(IdempotencyConflict):
            services.create_submission(
                agent,
                collection_ids=[collections[0].pk],
                declared_amount=Decimal("999.00"),
                idempotency_key=key,
            )

    def test_one_pending_submission_per_agent(self, receive_cash, submit, pending_submission):
        with pytest.raises(PendingSubmissionExists) as excinfo:
            submit(receive_cash("100.00"))

        assert excinfo.value.status_code == 409
        assert excinfo.value.details["submission_id"] == pending_submission.pk

    def test_other_agents_receipts_are_not_found(self, submit, other_agent_loan, receive_cash):
        theirs = receive_cash("1000.00", loan=other_agent_loan)

        with pytest.raises(ResourceNotFound) as excinfo:
            submit(theirs)

        assert excinfo.value.details == {"collection_ids": [theirs[0].pk]}

    def test_upi_receipts_cannot_be_handed_over(self, receive_cash, submit):
        upi = receive_cash("1000.00", upi=True)

        with pytest.raises(ValidationFailed) as excinfo:
            submit(upi)

        assert excinfo.value.details == {"receipt_numbers": [upi[0].receipt_number]}

    def test_receipts_already_handed_over_are_rejected(self, manager, receive_cash, submit):
        collection = receive_cash("1000.00")[0]
        services.approve_submission(manager, submit([collection]), received_amount=Decimal(1000))

        with pytest.raises(InvalidStateTransition) as excinfo:
            submit([collection])

        assert excinfo.value.details == {"receipt_numbers": [collection.receipt_number]}

    def test_voided_receipts_are_rejected(self, receive_cash, submit):
        collection = receive_cash("1000.00")[0]
        Collection.objects.filter(pk=collection.pk).update(
            status=Collection.Status.VOIDED, voided_at=collection.collected_at
        )

        with pytest.raises(InvalidStateTransition):
            submit([collection])

    def test_only_agents_can_submit(self, manager, receive_cash):
        collection = receive_cash("1000.00")[0]

        with pytest.raises(ScopeViolation):
            services.create_submission(
                manager,
                collection_ids=[collection.pk],
                declared_amount=Decimal("1000.00"),
                idempotency_key=uuid.uuid4(),
            )


class TestApproveSubmission:
    def test_exact_count_approves_without_discrepancy(self, manager, pending_submission):
        submission = services.approve_submission(
            manager, pending_submission, received_amount=Decimal("50000.00")
        )

        assert submission.status == Status.APPROVED
        assert submission.difference == Decimal("0.00")
        assert submission.reviewed_by == manager
        assert submission.reviewed_at is not None
        assert not submission.discrepancies.exists()
        collections = Collection.objects.filter(submission=submission)
        assert {c.status for c in collections} == {Collection.Status.BRANCH_RECEIVED}
        assert all(c.branch_received_at == submission.reviewed_at for c in collections)
        entry = _audit(AuditAction.SUBMISSION_APPROVED, submission)
        assert entry.before["status"] == Status.SUBMITTED
        assert entry.after["received_amount"] == "50000.00"

    def test_brief_example_shortage_of_1500(self, manager, agent, branch, pending_submission):
        submission = services.approve_submission(
            manager,
            pending_submission,
            received_amount=Decimal("48500.00"),
            denominations={"500": 97},
            reason_code=Discrepancy.ReasonCode.AGENT_SHORTAGE,
            remarks="  Agent short by 1500; will repay tomorrow. ",
        )

        assert submission.status == Status.APPROVED_WITH_DISCREPANCY
        assert submission.expected_amount == Decimal("50000.00")
        assert submission.received_amount == Decimal("48500.00")
        assert submission.difference == Decimal("1500.00")
        assert submission.review_remarks == "Agent short by 1500; will repay tomorrow."
        discrepancy = submission.discrepancies.get()
        assert discrepancy.kind == Discrepancy.Kind.CASH_SHORTAGE
        assert discrepancy.direction == Discrepancy.Direction.SHORT
        assert discrepancy.amount == Decimal("1500.00")
        assert discrepancy.status == Discrepancy.Status.OPEN
        assert discrepancy.agent == agent
        assert discrepancy.branch == branch
        assert discrepancy.raised_by == manager
        assert discrepancy.reason_code == Discrepancy.ReasonCode.AGENT_SHORTAGE
        assert _audit(AuditAction.DISCREPANCY_RAISED, discrepancy).after["amount"] == "1500.00"

    def test_excess_cash_opens_excess_discrepancy(self, manager, pending_submission):
        submission = services.approve_submission(
            manager,
            pending_submission,
            received_amount=Decimal("50200.00"),
            reason_code=Discrepancy.ReasonCode.COUNTING_ERROR,
            remarks="Agent's own money mixed in.",
        )

        assert submission.difference == Decimal("-200.00")
        discrepancy = submission.discrepancies.get()
        assert discrepancy.kind == Discrepancy.Kind.CASH_EXCESS
        assert discrepancy.direction == Discrepancy.Direction.EXCESS
        assert discrepancy.amount == Decimal("200.00")

    def test_nothing_received_is_a_full_shortage(self, manager, pending_submission):
        submission = services.approve_submission(
            manager,
            pending_submission,
            received_amount=Decimal("0.00"),
            reason_code=Discrepancy.ReasonCode.AGENT_SHORTAGE,
            remarks="Agent came without the cash.",
        )

        assert submission.discrepancies.get().amount == Decimal("50000.00")

    @pytest.mark.parametrize(
        ("reason_code", "remarks", "missing"),
        [
            ("", "Short.", {"reason_code"}),
            (Discrepancy.ReasonCode.OTHER, "   ", {"remarks"}),
            ("", "", {"reason_code", "remarks"}),
        ],
    )
    def test_difference_needs_reason_and_remarks(
        self, manager, pending_submission, reason_code, remarks, missing
    ):
        with pytest.raises(ValidationFailed) as excinfo:
            services.approve_submission(
                manager,
                pending_submission,
                received_amount=Decimal("48500.00"),
                reason_code=reason_code,
                remarks=remarks,
            )

        assert set(excinfo.value.details) - {"difference"} == missing
        pending_submission.refresh_from_db()
        assert pending_submission.status == Status.SUBMITTED

    def test_denominations_must_add_up_to_received_amount(self, manager, pending_submission):
        with pytest.raises(DenominationMismatch) as excinfo:
            services.approve_submission(
                manager,
                pending_submission,
                received_amount=Decimal("50000.00"),
                denominations={"500": 90, "200": 10},
            )

        assert excinfo.value.code == "DENOMINATION_MISMATCH"
        assert excinfo.value.details == {
            "denominations_total": "47000.00",
            "received_amount": "50000.00",
        }

    def test_double_approval_conflicts(self, manager, pending_submission):
        services.approve_submission(manager, pending_submission, received_amount=Decimal("50000"))

        with pytest.raises(InvalidStateTransition) as excinfo:
            services.approve_submission(
                manager, pending_submission, received_amount=Decimal("50000")
            )

        assert excinfo.value.status_code == 409
        assert excinfo.value.details["from"] == Status.APPROVED

    def test_admin_can_approve_any_branch(self, admin_user, pending_submission):
        submission = services.approve_submission(
            admin_user, pending_submission, received_amount=Decimal("50000.00")
        )

        assert submission.reviewed_by == admin_user

    @pytest.mark.parametrize("reviewer", ["other_branch_manager", "finance_user", "other_agent"])
    def test_only_branch_manager_or_admin_may_review(self, request, pending_submission, reviewer):
        with pytest.raises(ScopeViolation):
            services.approve_submission(
                request.getfixturevalue(reviewer),
                pending_submission,
                received_amount=Decimal("50000.00"),
            )

    def test_collector_cannot_verify_own_cash(self, agent, pending_submission):
        # An agent promoted to manager must not sign off on cash they handed over.
        agent.role = agent.Role.BRANCH_MANAGER
        agent.save(update_fields=["role"])

        with pytest.raises(SegregationOfDuties) as excinfo:
            services.approve_submission(
                agent, pending_submission, received_amount=Decimal("50000.00")
            )

        assert excinfo.value.status_code == 403

    def test_approved_submission_is_frozen_in_the_database(self, manager, pending_submission):
        services.approve_submission(manager, pending_submission, received_amount=Decimal("50000"))

        with (
            pytest.raises(DatabaseError, match="RECORD_LOCKED"),
            transaction.atomic(),
        ):
            CashSubmission.objects.filter(pk=pending_submission.pk).update(
                received_amount=Decimal("1.00")
            )
        with (
            pytest.raises(DatabaseError, match="RECORD_LOCKED"),
            transaction.atomic(),
        ):
            CashSubmission.objects.filter(pk=pending_submission.pk).update(
                received_denominations={"1": 1}
            )

    def test_branch_count_is_kept_apart_from_the_agents(self, manager, receive_cash, submit):
        pending = submit(receive_cash("1000.00"), denominations={"500": 2})

        submission = services.approve_submission(
            manager, pending, received_amount=Decimal("1000.00"), denominations={"100": 10}
        )

        assert submission.denominations == {"500": 2}
        assert submission.received_denominations == {"100": 10}
        entry = _audit(AuditAction.SUBMISSION_APPROVED, submission)
        assert entry.after["received_denominations"] == {"100": 10}

    def test_uncounted_hand_over_stays_uncounted_after_review(self, manager, pending_submission):
        submission = services.approve_submission(
            manager,
            pending_submission,
            received_amount=Decimal("50000.00"),
            denominations={"500": 100},
        )

        assert submission.denominations is None
        assert submission.received_denominations == {"500": 100}


class TestRejectSubmission:
    def test_returns_receipts_to_agent_and_keeps_history(self, manager, pending_submission):
        collection_ids = sorted(
            Collection.objects.filter(submission=pending_submission).values_list("pk", flat=True)
        )

        submission = services.reject_submission(
            manager, pending_submission, reason="  Receipts and cash do not match. "
        )

        assert submission.status == Status.REJECTED
        assert submission.rejection_reason == "Receipts and cash do not match."
        assert submission.received_amount is None
        for collection in Collection.objects.filter(pk__in=collection_ids):
            assert collection.status == Collection.Status.COLLECTED
            assert collection.submission is None
            assert collection.submitted_at is None
        entry = _audit(AuditAction.SUBMISSION_REJECTED, submission)
        assert entry.before["collection_ids"] == collection_ids
        assert sorted(c.pk for c in selectors.submission_collections(submission)) == collection_ids

    def test_agent_can_resubmit_after_rejection(self, manager, submit, pending_submission):
        services.reject_submission(manager, pending_submission, reason="Recount.")
        returned = list(Collection.objects.filter(status=Collection.Status.COLLECTED))

        resubmission = submit(returned)

        assert resubmission != pending_submission
        assert resubmission.expected_amount == Decimal("50000.00")
        assert Collection.objects.filter(submission=resubmission).count() == 2

    def test_reason_is_required(self, manager, pending_submission):
        with pytest.raises(ValidationFailed):
            services.reject_submission(manager, pending_submission, reason="   ")

    def test_cannot_reject_after_approval(self, manager, pending_submission):
        services.approve_submission(manager, pending_submission, received_amount=Decimal("50000"))

        with pytest.raises(InvalidStateTransition):
            services.reject_submission(manager, pending_submission, reason="Changed my mind.")

    def test_other_branch_manager_cannot_reject(self, other_branch_manager, pending_submission):
        with pytest.raises(ScopeViolation):
            services.reject_submission(other_branch_manager, pending_submission, reason="No.")
