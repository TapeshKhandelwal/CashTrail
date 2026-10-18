"""Cash hand-over from agents, branch verification, and the discrepancy workflow."""

import uuid
from collections.abc import Iterable, Mapping
from decimal import Decimal

from django.db import transaction
from django.db.models import Model
from django.utils import timezone

from apps.accounts.scoping import scope_queryset
from apps.audit.models import AuditAction
from apps.audit.services import log_event, snapshot
from apps.collections.models import Collection
from apps.collections.services import lock_collections, move_collections
from apps.core.exceptions import (
    IdempotencyConflict,
    InvalidStateTransition,
    ResourceNotFound,
    ScopeViolation,
    ValidationFailed,
)
from apps.core.idempotency import lock_idempotency_key
from apps.core.money import ZERO, to_money
from apps.core.numbering import submission_number
from apps.deposits.models import BankDeposit

from . import selectors
from .denominations import denominations_total, normalize_denominations
from .exceptions import DenominationMismatch, PendingSubmissionExists, SegregationOfDuties
from .models import CashSubmission, Discrepancy, SubmissionItem

SUBMISSION_AUDIT_FIELDS = (
    "status",
    "expected_amount",
    "declared_amount",
    "received_amount",
    "denominations",
    "received_denominations",
    "reviewed_by",
    "reviewed_at",
    "review_remarks",
    "rejection_reason",
)
DISCREPANCY_AUDIT_FIELDS = (
    "kind",
    "direction",
    "amount",
    "submission",
    "deposit",
    "agent",
    "status",
    "reason_code",
    "notes",
    "resolution_notes",
    "resolved_by",
    "resolved_at",
)

# Deposit-side discrepancy kinds and the deposit source each one applies to.
DEPOSIT_KIND_SOURCES = {
    Discrepancy.Kind.DEPOSIT_MISMATCH: BankDeposit.Source.CASH,
    Discrepancy.Kind.SETTLEMENT_MISMATCH: BankDeposit.Source.CASH,
    Discrepancy.Kind.GATEWAY_MISMATCH: BankDeposit.Source.GATEWAY,
}
CASH_KIND_DIRECTIONS = {
    Discrepancy.Kind.CASH_SHORTAGE: Discrepancy.Direction.SHORT,
    Discrepancy.Kind.CASH_EXCESS: Discrepancy.Direction.EXCESS,
}
RESOLUTION_ACTIONS = {
    Discrepancy.Status.RESOLVED: AuditAction.DISCREPANCY_RESOLVED,
    Discrepancy.Status.WRITTEN_OFF: AuditAction.DISCREPANCY_WRITTEN_OFF,
}


# Cash submissions


def create_submission(
    actor,
    *,
    collection_ids: Iterable[int],
    declared_amount: Decimal,
    idempotency_key: uuid.UUID,
    denominations: Mapping[str, int] | None = None,
) -> tuple[CashSubmission, bool]:
    """Hand a batch of the agent's cash receipts over to the branch.

    Returns `(submission, created)`; a retry with the same key returns the original.
    """
    if not actor.is_agent:
        raise ScopeViolation("Only collection agents can submit cash to a branch.")
    ids = sorted(set(collection_ids))
    if not ids:
        raise ValidationFailed("Select at least one receipt to submit.")
    declared = to_money(declared_amount)
    if declared < ZERO:
        raise ValidationFailed("The declared amount cannot be negative.")
    counts = _counted(denominations, declared, field="declared_amount")

    with transaction.atomic():
        lock_idempotency_key("submission", actor.pk, idempotency_key)
        existing = CashSubmission.objects.filter(
            agent=actor, idempotency_key=idempotency_key
        ).first()
        if existing is not None:
            _ensure_same_submission(existing, ids, declared, counts)
            return existing, False

        pending = CashSubmission.objects.filter(
            agent=actor, status=CashSubmission.Status.SUBMITTED
        ).first()
        if pending is not None:
            raise PendingSubmissionExists(
                details={
                    "submission_id": pending.pk,
                    "submission_number": pending.submission_number,
                }
            )

        collections = list(
            Collection.objects.select_for_update().filter(agent=actor, pk__in=ids).order_by("pk")
        )
        _ensure_submittable(actor, collections, ids)

        now = timezone.now()
        submission = CashSubmission.objects.create(
            submission_number=submission_number(actor.branch.code),
            agent=actor,
            branch_id=actor.branch_id,
            expected_amount=sum((collection.amount for collection in collections), ZERO),
            declared_amount=declared,
            denominations=counts,
            submitted_at=now,
            idempotency_key=idempotency_key,
        )
        SubmissionItem.objects.bulk_create(
            SubmissionItem(submission=submission, collection=collection)
            for collection in collections
        )
        move_collections(
            collections, Collection.Status.SUBMITTED, submission=submission, submitted_at=now
        )
        log_event(
            actor,
            AuditAction.SUBMISSION_CREATED,
            submission,
            after={**snapshot(submission, SUBMISSION_AUDIT_FIELDS), "collection_ids": ids},
        )
    return submission, True


def approve_submission(
    actor,
    submission: CashSubmission,
    *,
    received_amount: Decimal,
    denominations: Mapping[str, int] | None = None,
    reason_code: str = "",
    remarks: str = "",
) -> CashSubmission:
    """Record the cash counted at the branch; any difference opens a cash discrepancy."""
    received = to_money(received_amount)
    if received < ZERO:
        raise ValidationFailed("The received amount cannot be negative.")
    remarks = remarks.strip()

    with transaction.atomic():
        submission = _lock_for_review(actor, submission)
        counts = _counted(denominations, received, field="received_amount")
        difference = submission.expected_amount - received
        if difference:
            _ensure_discrepancy_explained(difference, reason_code, remarks)

        before = snapshot(submission, SUBMISSION_AUDIT_FIELDS)
        now = timezone.now()
        submission.transition_to(
            CashSubmission.Status.APPROVED_WITH_DISCREPANCY
            if difference
            else CashSubmission.Status.APPROVED
        )
        submission.received_amount = received
        submission.received_denominations = counts
        submission.reviewed_at = now
        submission.reviewed_by = actor
        submission.review_remarks = remarks
        submission.save(
            update_fields=[
                "status",
                "received_amount",
                "received_denominations",
                "reviewed_at",
                "reviewed_by",
                "review_remarks",
                "updated_at",
            ]
        )
        move_collections(
            lock_collections(submission.collections.all()),
            Collection.Status.BRANCH_RECEIVED,
            branch_received_at=now,
        )
        log_event(
            actor,
            AuditAction.SUBMISSION_APPROVED,
            submission,
            before=before,
            after=snapshot(submission, SUBMISSION_AUDIT_FIELDS),
        )
        if difference:
            record_discrepancy(
                kind=(
                    Discrepancy.Kind.CASH_SHORTAGE
                    if difference > 0
                    else Discrepancy.Kind.CASH_EXCESS
                ),
                amount=abs(difference),
                submission=submission,
                reason_code=reason_code,
                notes=remarks,
                raised_by=actor,
            )
    return submission


def reject_submission(actor, submission: CashSubmission, *, reason: str) -> CashSubmission:
    """Send the receipts back to the agent; the rejected submission stays for the record."""
    reason = reason.strip()
    if not reason:
        raise ValidationFailed("A reason is required to reject a submission.")

    with transaction.atomic():
        submission = _lock_for_review(actor, submission)
        before = snapshot(submission, SUBMISSION_AUDIT_FIELDS)
        submission.transition_to(CashSubmission.Status.REJECTED)
        submission.reviewed_at = timezone.now()
        submission.reviewed_by = actor
        submission.rejection_reason = reason
        submission.save(
            update_fields=[
                "status",
                "reviewed_at",
                "reviewed_by",
                "rejection_reason",
                "updated_at",
            ]
        )
        # The receipts go back to the agent; the submission's items keep what was handed over.
        released = move_collections(
            lock_collections(submission.collections.all()),
            Collection.Status.COLLECTED,
            submission=None,
            submitted_at=None,
        )
        log_event(
            actor,
            AuditAction.SUBMISSION_REJECTED,
            submission,
            before={**before, "collection_ids": released},
            after=snapshot(submission, SUBMISSION_AUDIT_FIELDS),
        )
    return submission


def _counted(
    denominations: Mapping[str, int] | None, amount: Decimal, *, field: str
) -> dict[str, int] | None:
    if denominations is None:
        return None
    try:
        counts = normalize_denominations(denominations)
    except ValueError as exc:
        raise ValidationFailed(str(exc), details={"denominations": str(exc)}) from None
    total = denominations_total(counts)
    if total != amount:
        raise DenominationMismatch(details={"denominations_total": str(total), field: str(amount)})
    return counts or None


def _ensure_same_submission(
    submission: CashSubmission,
    collection_ids: list[int],
    declared: Decimal,
    counts: dict[str, int] | None,
) -> None:
    stored_ids = sorted(selectors.submission_collections(submission).values_list("pk", flat=True))
    if (
        stored_ids != collection_ids
        or submission.declared_amount != declared
        or submission.denominations != counts
    ):
        raise IdempotencyConflict(details={"submission_id": submission.pk})


def _ensure_submittable(actor, collections: list[Collection], requested_ids: list[int]) -> None:
    missing = sorted(set(requested_ids) - {collection.pk for collection in collections})
    if missing:
        raise ResourceNotFound(
            "Some receipts were not found among your collections.",
            details={"collection_ids": missing},
        )
    not_cash = [c.receipt_number for c in collections if c.mode != Collection.Mode.CASH]
    if not_cash:
        raise ValidationFailed(
            "Only cash receipts are handed over to the branch.",
            details={"receipt_numbers": not_cash},
        )
    other_branch = [c.receipt_number for c in collections if c.branch_id != actor.branch_id]
    if other_branch:
        raise ValidationFailed(
            "Receipts from another branch cannot be submitted here.",
            details={"receipt_numbers": other_branch},
        )
    unavailable = [c.receipt_number for c in collections if c.status != Collection.Status.COLLECTED]
    if unavailable:
        raise InvalidStateTransition(
            "Some receipts are no longer in hand (already submitted or voided).",
            details={"receipt_numbers": unavailable},
        )


def _lock_for_review(actor, submission: CashSubmission) -> CashSubmission:
    locked = CashSubmission.objects.select_for_update().get(pk=submission.pk)
    if not (actor.is_admin or (actor.is_branch_manager and actor.branch_id == locked.branch_id)):
        raise ScopeViolation("Only the branch's manager or an admin can review this submission.")
    if actor.pk == locked.agent_id:
        raise SegregationOfDuties()
    if locked.is_locked:
        raise InvalidStateTransition(
            f"Submission {locked.submission_number} has already been reviewed.",
            details={"entity": "cashsubmission", "id": locked.pk, "from": locked.status},
        )
    return locked


def _ensure_discrepancy_explained(difference: Decimal, reason_code: str, remarks: str) -> None:
    missing = {}
    if reason_code not in Discrepancy.ReasonCode.values:
        missing["reason_code"] = "Choose why the counted cash differs."
    if not remarks:
        missing["remarks"] = "Explain the difference."
    if missing:
        raise ValidationFailed(
            "The counted cash differs from the expected amount; a reason code and remarks "
            "are required.",
            details={"difference": str(difference), **missing},
        )


# Discrepancies


def record_discrepancy(
    *,
    kind: str,
    amount: Decimal,
    reason_code: str,
    raised_by,
    submission: CashSubmission | None = None,
    deposit: BankDeposit | None = None,
    direction: str | None = None,
    notes: str = "",
) -> Discrepancy:
    """Open a discrepancy against the checkpoint record where the difference surfaced.

    Callers decide who may raise it; `raised_by` is None for system-detected differences.
    """
    amount = to_money(amount)
    if amount <= ZERO:
        raise ValidationFailed("A discrepancy amount must be greater than zero.")
    if reason_code not in Discrepancy.ReasonCode.values:
        raise ValidationFailed("Unknown reason code.", details={"reason_code": reason_code})

    if kind in Discrepancy.CASH_KINDS:
        if submission is None or deposit is not None:
            raise ValidationFailed("Cash discrepancies are raised against a cash submission.")
        expected_direction = CASH_KIND_DIRECTIONS[kind]
        if direction not in (None, expected_direction):
            raise ValidationFailed(
                f"A {kind} discrepancy is always {expected_direction}.",
                details={"direction": direction},
            )
        direction = expected_direction
        source: Model = submission
        agent_id = submission.agent_id
    elif kind in DEPOSIT_KIND_SOURCES:
        if deposit is None or submission is not None:
            raise ValidationFailed("This kind of discrepancy is raised against a bank deposit.")
        if direction not in Discrepancy.Direction.values:
            raise ValidationFailed(
                "Say whether the amount was short or in excess.", details={"direction": direction}
            )
        source = deposit
        agent_id = None
    else:
        raise ValidationFailed("Unknown discrepancy kind.", details={"kind": kind})

    with transaction.atomic():
        discrepancy = Discrepancy.objects.create(
            kind=kind,
            direction=direction,
            amount=amount,
            submission=submission,
            deposit=deposit,
            branch_id=source.branch_id,
            agent_id=agent_id,
            reason_code=reason_code,
            notes=notes.strip(),
            raised_by=raised_by,
        )
        log_event(
            raised_by,
            AuditAction.DISCREPANCY_RAISED,
            discrepancy,
            after=snapshot(discrepancy, DISCREPANCY_AUDIT_FIELDS),
        )
    return discrepancy


def raise_discrepancy(
    actor,
    *,
    kind: str,
    amount: Decimal,
    reason_code: str,
    notes: str,
    direction: str | None = None,
    submission_id: int | None = None,
    deposit_id: int | None = None,
) -> Discrepancy:
    """Manually record a difference found after the fact, e.g. a counterfeit note."""
    _ensure_can_raise(actor, kind)
    if not notes.strip():
        raise ValidationFailed("Describe the discrepancy.", details={"notes": "Required."})

    with transaction.atomic():
        if kind in Discrepancy.CASH_KINDS:
            if submission_id is None or deposit_id is not None:
                raise ValidationFailed(
                    "Cash discrepancies are raised against a cash submission.",
                    details={"submission_id": "Required."},
                )
            submission = _scoped_for_update(CashSubmission, actor, submission_id)
            if not submission.is_approved:
                raise ValidationFailed(
                    "Only an approved submission can carry a cash discrepancy.",
                    details={"status": submission.status},
                )
            return record_discrepancy(
                kind=kind,
                amount=amount,
                reason_code=reason_code,
                raised_by=actor,
                submission=submission,
                direction=direction,
                notes=notes,
            )

        if deposit_id is None or submission_id is not None:
            raise ValidationFailed(
                "This kind of discrepancy is raised against a bank deposit.",
                details={"deposit_id": "Required."},
            )
        deposit = _scoped_for_update(BankDeposit, actor, deposit_id)
        expected_source = DEPOSIT_KIND_SOURCES.get(kind)
        if deposit.source != expected_source:
            raise ValidationFailed(
                f"A {kind} discrepancy does not apply to a {deposit.source} deposit.",
                details={"kind": kind, "source": deposit.source},
            )
        if deposit.status == BankDeposit.Status.FAILED:
            raise ValidationFailed("A failed deposit cannot carry a discrepancy.")
        return record_discrepancy(
            kind=kind,
            amount=amount,
            reason_code=reason_code,
            raised_by=actor,
            deposit=deposit,
            direction=direction,
            notes=notes,
        )


def resolve_discrepancy(
    actor, discrepancy: Discrepancy, *, outcome: str, resolution_notes: str
) -> Discrepancy:
    """Close an open discrepancy as recovered/explained (RESOLVED) or WRITTEN_OFF."""
    if outcome not in RESOLUTION_ACTIONS:
        raise ValidationFailed(
            "Outcome must be RESOLVED or WRITTEN_OFF.", details={"outcome": outcome}
        )
    resolution_notes = resolution_notes.strip()
    if not resolution_notes:
        raise ValidationFailed(
            "Resolution notes are required.", details={"resolution_notes": "Required."}
        )

    with transaction.atomic():
        discrepancy = Discrepancy.objects.select_for_update().get(pk=discrepancy.pk)
        _ensure_can_resolve(actor, discrepancy)
        before = snapshot(discrepancy, DISCREPANCY_AUDIT_FIELDS)
        discrepancy.transition_to(outcome)
        discrepancy.resolution_notes = resolution_notes
        discrepancy.resolved_by = actor
        discrepancy.resolved_at = timezone.now()
        discrepancy.save(
            update_fields=[
                "status",
                "resolution_notes",
                "resolved_by",
                "resolved_at",
                "updated_at",
            ]
        )
        log_event(
            actor,
            RESOLUTION_ACTIONS[outcome],
            discrepancy,
            before=before,
            after=snapshot(discrepancy, DISCREPANCY_AUDIT_FIELDS),
        )
    return discrepancy


def _ensure_can_raise(actor, kind: str) -> None:
    if actor.is_admin:
        return
    if actor.is_branch_manager and (
        kind in Discrepancy.CASH_KINDS or kind == Discrepancy.Kind.DEPOSIT_MISMATCH
    ):
        return
    if actor.is_finance and kind in DEPOSIT_KIND_SOURCES:
        return
    raise ScopeViolation("Your role cannot raise this kind of discrepancy.")


def _ensure_can_resolve(actor, discrepancy: Discrepancy) -> None:
    """Branch managers own cash differences; finance owns bank and gateway differences."""
    if actor.is_admin:
        return
    if discrepancy.is_cash:
        if actor.is_branch_manager and actor.branch_id == discrepancy.branch_id:
            return
        raise ScopeViolation("Cash discrepancies are resolved by the branch manager or an admin.")
    if actor.is_finance:
        return
    raise ScopeViolation("Deposit and settlement discrepancies are resolved by finance.")


def _scoped_for_update(model: type[Model], actor, pk: int):
    """Lock a record the actor can see; anything outside their scope is reported as missing."""
    queryset = scope_queryset(model.objects.select_for_update(), actor)
    try:
        return queryset.get(pk=pk)
    except model.DoesNotExist:
        raise ResourceNotFound(
            f"{model._meta.verbose_name.capitalize()} not found.", details={"id": pk}
        ) from None
