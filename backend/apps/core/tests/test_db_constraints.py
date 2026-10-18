"""Representative database guarantees; they hold even if a service has a bug."""

from decimal import Decimal

import pytest
from django.db import IntegrityError
from django.utils import timezone

from apps.collections.models import Collection
from apps.core.testing import factories
from apps.reconciliation.models import CashSubmission, Discrepancy

pytestmark = pytest.mark.django_db


def violates(constraint):
    return pytest.raises(IntegrityError, match=constraint)


def test_loan_cannot_be_overpaid(loan):
    loan.amount_paid = loan.total_payable + Decimal("0.01")

    with violates("loan_amount_paid_within_total"):
        loan.save()


def test_installment_status_must_match_amount_paid(loan):
    installment = loan.installments.first()
    installment.amount_paid = Decimal("100.00")

    with violates("installment_status_matches_amount_paid"):
        installment.save()


def test_installment_sync_status_keeps_constraint(loan):
    installment = loan.installments.first()
    installment.amount_paid = installment.amount_due
    installment.sync_status()
    installment.save()

    assert installment.status == "PAID"
    assert installment.paid_at is not None


def test_cash_collection_needs_an_agent(loan):
    with violates("collection_mode_consistency"):
        factories.CollectionFactory(loan=loan, agent=None)


def test_same_idempotency_key_cannot_create_two_collections(loan):
    first = factories.CollectionFactory(loan=loan)

    with violates("uniq_collection_agent_idempotency_key"):
        factories.CollectionFactory(loan=loan, idempotency_key=first.idempotency_key)


def test_gateway_payment_recorded_once(loan):
    first = factories.CollectionFactory(loan=loan, upi=True)

    with violates("uniq_collection_gateway_payment_id"):
        factories.CollectionFactory(
            loan=loan, upi=True, gateway_payment_id=first.gateway_payment_id
        )


def test_submitted_cash_collection_requires_submission(loan):
    with violates("collection_cash_in_branch_has_submission"):
        factories.CollectionFactory(loan=loan, status=Collection.Status.SUBMITTED)


def test_one_pending_submission_per_agent(agent):
    factories.CashSubmissionFactory(agent=agent)

    with violates("uniq_submission_pending_per_agent"):
        factories.CashSubmissionFactory(agent=agent)


def test_reviewed_submissions_do_not_block_new_ones(agent):
    factories.CashSubmissionFactory(agent=agent, approved=True)
    factories.CashSubmissionFactory(agent=agent, rejected=True)

    assert factories.CashSubmissionFactory(agent=agent).status == CashSubmission.Status.SUBMITTED


def test_submission_difference_is_generated(agent):
    submission = factories.CashSubmissionFactory(
        agent=agent, expected_amount=Decimal("50000.00"), short=True
    )
    submission.refresh_from_db()

    assert submission.received_amount == Decimal("49500.00")
    assert submission.difference == Decimal("500.00")


def test_plain_approval_requires_matching_amount(agent, manager):
    with violates("submission_review_consistency"):
        factories.CashSubmissionFactory(
            agent=agent,
            status=CashSubmission.Status.APPROVED,
            received_amount=Decimal("1.00"),
            reviewed_at=timezone.now(),
            reviewed_by=manager,
        )


def test_duplicate_bank_reference_is_case_insensitive(bank_account, branch, manager):
    factories.BankDepositFactory(
        bank_account=bank_account, branch=branch, created_by=manager, reference_number="ABC123"
    )

    with violates("uniq_bank_deposit_account_reference"):
        factories.BankDepositFactory(
            bank_account=bank_account,
            branch=branch,
            created_by=manager,
            reference_number=" abc 123",
        )


def test_gateway_deposit_has_no_branch(branch):
    with violates("bank_deposit_branch_matches_source"):
        factories.BankDepositFactory(gateway=True, branch=branch)


def test_discrepancy_has_exactly_one_source():
    deposit = factories.BankDepositFactory()

    with violates("discrepancy_single_source"):
        factories.DiscrepancyFactory(deposit=deposit)


def test_resolved_discrepancy_requires_notes():
    with violates("discrepancy_resolution_consistency"):
        factories.DiscrepancyFactory(status=Discrepancy.Status.RESOLVED, resolved_at=timezone.now())
