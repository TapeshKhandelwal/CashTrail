"""Bank deposits of branch cash, their settlement, and gateway settlements of UPI collections."""

import logging
import uuid
from collections.abc import Iterable
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditLog
from apps.audit.services import log_event, snapshot
from apps.collections.models import Collection
from apps.collections.services import lock_collections, move_collections
from apps.core.dates import business_date, day_bounds
from apps.core.exceptions import (
    DomainError,
    DuplicateBankReference,
    IdempotencyConflict,
    RecordLocked,
    ResourceNotFound,
    ScopeViolation,
    ValidationFailed,
)
from apps.core.idempotency import lock_idempotency_key
from apps.core.money import ZERO, to_money
from apps.core.numbering import deposit_number
from apps.reconciliation.models import CashSubmission, Discrepancy
from apps.reconciliation.services import record_discrepancy, resolve_discrepancy

from . import selectors
from .exceptions import SubmissionAlreadyDeposited
from .models import BankAccount, BankDeposit, normalize_reference

logger = logging.getLogger(__name__)

GATEWAY_SCOPE = "GATEWAY"
IDEMPOTENCY_SCOPE = "deposit"
# Upper bound on the payments one gateway settlement may lock and settle.
MAX_SETTLEMENT_ITEMS = 5_000

DEPOSIT_AUDIT_FIELDS = (
    "deposit_number",
    "source",
    "branch",
    "bank_account",
    "reference_number",
    "deposit_date",
    "expected_amount",
    "deposited_amount",
    "fee_amount",
    "tax_amount",
    "settled_amount",
    "settled_on",
    "settlement_reference",
    "status",
)
BANK_ACCOUNT_FIELDS = (
    "bank_name",
    "account_name",
    "account_number_last4",
    "ifsc",
    "is_gateway",
    "is_active",
)
# Fields that identify where money landed; frozen once any deposit points at the account.
BANK_ACCOUNT_IDENTITY_FIELDS = frozenset(
    {"bank_name", "account_number_last4", "ifsc", "is_gateway"}
)


def _require_role(actor: User, *roles: str) -> None:
    if actor.role not in roles:
        raise ScopeViolation(details={"role": actor.role})


def _require_not_future(day: date, field: str) -> None:
    if day > business_date():
        raise ValidationFailed(f"{field} cannot be in the future.", details={field: day})


def _ensure_unused_reference(account: BankAccount, reference: str) -> None:
    if BankDeposit.objects.filter(bank_account=account, reference_number=reference).exists():
        raise DuplicateBankReference(
            details={"bank_account_id": account.pk, "reference_number": reference}
        )


def _raise_discrepancy(
    actor: User,
    deposit: BankDeposit,
    *,
    kind: str,
    shortfall: Decimal,
    reason_code: str,
    notes: str,
) -> Discrepancy:
    """A positive shortfall means less money arrived than expected."""
    return record_discrepancy(
        kind=kind,
        amount=abs(shortfall),
        direction=Discrepancy.Direction.SHORT if shortfall > 0 else Discrepancy.Direction.EXCESS,
        reason_code=reason_code,
        raised_by=actor,
        deposit=deposit,
        notes=notes,
    )


# Bank accounts ----------------------------------------------------------------------------


@transaction.atomic
def create_bank_account(actor: User, **fields) -> BankAccount:
    _require_role(actor, User.Role.ADMIN)
    if fields.get("is_gateway") and fields.get("is_active", True):
        _ensure_no_other_active_gateway_account()
    account = BankAccount.objects.create(**fields)
    log_event(
        actor,
        AuditAction.BANK_ACCOUNT_CREATED,
        account,
        after=snapshot(account, BANK_ACCOUNT_FIELDS),
    )
    return account


@transaction.atomic
def update_bank_account(actor: User, account: BankAccount, **changes) -> BankAccount:
    _require_role(actor, User.Role.ADMIN)
    account = BankAccount.objects.select_for_update().get(pk=account.pk)
    changed = {field: value for field, value in changes.items() if getattr(account, field) != value}
    if not changed:
        return account

    locked = sorted(BANK_ACCOUNT_IDENTITY_FIELDS & changed.keys())
    if locked and account.deposits.exists():
        raise RecordLocked(
            "Bank details cannot change once deposits reference this account.",
            details={"fields": locked},
        )
    becomes_active_gateway = changed.get("is_gateway", account.is_gateway) and changed.get(
        "is_active", account.is_active
    )
    if becomes_active_gateway:
        _ensure_no_other_active_gateway_account(exclude=account)

    before = snapshot(account, changed)
    for field, value in changed.items():
        setattr(account, field, value)
    account.save(update_fields=[*changed, "updated_at"])
    log_event(
        actor,
        AuditAction.BANK_ACCOUNT_UPDATED,
        account,
        before=before,
        after=snapshot(account, changed),
    )
    return account


def _ensure_no_other_active_gateway_account(exclude: BankAccount | None = None) -> None:
    others = BankAccount.objects.filter(is_gateway=True, is_active=True)
    if exclude is not None:
        others = others.exclude(pk=exclude.pk)
    if others.exists():
        raise DomainError(
            "Only one active gateway settlement account is allowed.",
            code="GATEWAY_ACCOUNT_EXISTS",
            status_code=409,
        )


# Cash deposits ----------------------------------------------------------------------------


@transaction.atomic
def create_deposit(
    actor: User,
    *,
    submission_ids: Iterable[int],
    bank_account_id: int,
    deposited_amount: Decimal,
    deposit_date: date,
    reference_number: str,
    remarks: str = "",
    idempotency_key: uuid.UUID,
) -> tuple[BankDeposit, bool]:
    """Deposit approved, undeposited branch cash. Returns `(deposit, created)`."""
    _require_role(actor, User.Role.ADMIN, User.Role.BRANCH_MANAGER)
    submission_ids = sorted(set(submission_ids))
    deposited_amount = to_money(deposited_amount)
    reference = normalize_reference(reference_number)
    remarks = remarks.strip()

    lock_idempotency_key(IDEMPOTENCY_SCOPE, actor.pk, idempotency_key)
    existing = BankDeposit.objects.filter(created_by=actor, idempotency_key=idempotency_key).first()
    if existing is not None:
        replay = (
            existing.bank_account_id == bank_account_id
            and existing.deposited_amount == deposited_amount
            and existing.deposit_date == deposit_date
            and existing.reference_number == reference
            and selectors.deposited_submission_ids(existing) == submission_ids
        )
        if not replay:
            raise IdempotencyConflict(details={"deposit_number": existing.deposit_number})
        return existing, False

    if not reference:
        raise ValidationFailed("A bank reference number is required.")
    _require_not_future(deposit_date, "deposit_date")
    account = _get_cash_account(bank_account_id)
    submissions = _lock_depositable_submissions(actor, submission_ids)
    branch = submissions[0].branch

    latest_approval = business_date(max(s.reviewed_at for s in submissions))
    if deposit_date < latest_approval:
        raise ValidationFailed(
            "The deposit date cannot be before the cash was approved at the branch.",
            details={"deposit_date": deposit_date, "latest_approval_date": latest_approval},
        )

    expected_amount = sum((s.received_amount for s in submissions), ZERO)
    shortfall = expected_amount - deposited_amount
    if shortfall and not remarks:
        raise ValidationFailed(
            "Remarks are required when the deposited amount differs from the reconciled cash.",
            details={
                "expected_amount": str(expected_amount),
                "deposited_amount": str(deposited_amount),
                "difference": str(shortfall),
            },
        )
    _ensure_unused_reference(account, reference)

    collections = lock_collections(Collection.objects.filter(submission__in=submissions))
    now = timezone.now()
    deposit = BankDeposit.objects.create(
        deposit_number=deposit_number(branch.code),
        source=BankDeposit.Source.CASH,
        branch=branch,
        bank_account=account,
        reference_number=reference,
        deposit_date=deposit_date,
        expected_amount=expected_amount,
        deposited_amount=deposited_amount,
        remarks=remarks,
        created_by=actor,
        idempotency_key=idempotency_key,
    )
    CashSubmission.objects.filter(pk__in=[s.pk for s in submissions]).update(
        deposit=deposit, updated_at=now
    )
    move_collections(collections, Collection.Status.DEPOSITED, deposit=deposit, deposited_at=now)

    log_event(
        actor,
        AuditAction.DEPOSIT_CREATED,
        deposit,
        after={
            **snapshot(deposit, DEPOSIT_AUDIT_FIELDS),
            "submission_ids": [s.pk for s in submissions],
            "collection_ids": [c.pk for c in collections],
        },
    )
    if shortfall:
        _raise_discrepancy(
            actor,
            deposit,
            kind=Discrepancy.Kind.DEPOSIT_MISMATCH,
            shortfall=shortfall,
            reason_code=Discrepancy.ReasonCode.OTHER,
            notes=remarks,
        )
    return deposit, True


def _get_cash_account(bank_account_id: int) -> BankAccount:
    account = BankAccount.objects.filter(pk=bank_account_id, is_active=True).first()
    if account is None:
        raise ResourceNotFound(
            "Bank account not found or inactive.", details={"bank_account_id": bank_account_id}
        )
    if account.is_gateway:
        raise ValidationFailed(
            "Cash cannot be deposited into the gateway settlement account.",
            details={"bank_account_id": bank_account_id},
        )
    return account


def _lock_depositable_submissions(
    actor: User, submission_ids: Iterable[int]
) -> list[CashSubmission]:
    ids = sorted(set(submission_ids))
    if not ids:
        raise ValidationFailed("Select at least one approved submission to deposit.")

    queryset = CashSubmission.objects.select_for_update().filter(pk__in=ids).order_by("pk")
    if actor.is_branch_manager:
        queryset = queryset.filter(branch_id=actor.branch_id)
    submissions = list(queryset)
    missing = sorted(set(ids) - {s.pk for s in submissions})
    if missing:
        raise ResourceNotFound("Submission not found.", details={"submission_ids": missing})

    if len({s.branch_id for s in submissions}) > 1:
        raise ValidationFailed("A deposit can only carry cash from a single branch.")
    not_approved = [s.pk for s in submissions if not s.is_approved]
    if not_approved:
        raise ValidationFailed(
            "Only approved submissions can be deposited.",
            details={"submission_ids": not_approved},
        )
    deposited = [s.pk for s in submissions if s.deposit_id is not None]
    if deposited:
        raise SubmissionAlreadyDeposited(details={"submission_ids": deposited})
    return submissions


@transaction.atomic
def settle_deposit(
    actor: User,
    deposit: BankDeposit,
    *,
    settled_amount: Decimal,
    settled_on: date,
    settlement_reference: str,
    remarks: str = "",
    reason_code: str = Discrepancy.ReasonCode.BANK_ERROR,
) -> BankDeposit:
    """Confirm the credit on the bank statement; differences become a settlement discrepancy.

    `reason_code` classifies that discrepancy, e.g. BANK_CHARGES for cash-handling fees.
    """
    _require_role(actor, User.Role.ADMIN, User.Role.FINANCE)
    deposit = BankDeposit.objects.select_for_update().get(pk=deposit.pk)
    _require_checker(actor, deposit)
    settled_amount = to_money(settled_amount)
    settlement_reference = settlement_reference.strip()
    remarks = remarks.strip()

    _require_not_future(settled_on, "settled_on")
    if settled_on < deposit.deposit_date:
        raise ValidationFailed(
            "A deposit cannot settle before it was made.",
            details={"settled_on": settled_on, "deposit_date": deposit.deposit_date},
        )
    shortfall = deposit.deposited_amount - settled_amount
    target = BankDeposit.Status.SETTLED_WITH_MISMATCH if shortfall else BankDeposit.Status.SETTLED
    before = snapshot(deposit, ["status", "settled_amount", "settled_on"])
    deposit.transition_to(target)
    if shortfall and not remarks:
        raise ValidationFailed(
            "Remarks are required when the settled amount differs from the deposit.",
            details={
                "deposited_amount": str(deposit.deposited_amount),
                "settled_amount": str(settled_amount),
                "difference": str(shortfall),
            },
        )

    now = timezone.now()
    collections = lock_collections(deposit.collections.all())
    deposit.settled_amount = settled_amount
    deposit.settled_on = settled_on
    deposit.settlement_reference = settlement_reference
    deposit.settled_at = now
    deposit.settled_by = actor
    deposit.save(
        update_fields=[
            "status",
            "settled_amount",
            "settled_on",
            "settlement_reference",
            "settled_at",
            "settled_by",
            "updated_at",
        ]
    )
    move_collections(collections, Collection.Status.SETTLED, settled_at=now)

    log_event(
        actor,
        AuditAction.DEPOSIT_SETTLED,
        deposit,
        before=before,
        after={
            **snapshot(deposit, ["status", "settled_amount", "settled_on", "settlement_reference"]),
            "collection_ids": [c.pk for c in collections],
            "remarks": remarks,
        },
    )
    if shortfall:
        _raise_discrepancy(
            actor,
            deposit,
            kind=Discrepancy.Kind.SETTLEMENT_MISMATCH,
            shortfall=shortfall,
            reason_code=reason_code,
            notes=remarks,
        )
    return deposit


@transaction.atomic
def fail_deposit(actor: User, deposit: BankDeposit, *, reason: str) -> BankDeposit:
    """The bank rejected or never credited the deposit: return the cash to the branch."""
    _require_role(actor, User.Role.ADMIN, User.Role.FINANCE)
    deposit = BankDeposit.objects.select_for_update().get(pk=deposit.pk)
    _require_checker(actor, deposit)
    reason = reason.strip()
    if not reason:
        raise ValidationFailed("A failure reason is required.")

    before = snapshot(deposit, ["status"])
    deposit.transition_to(BankDeposit.Status.FAILED)
    submissions = list(
        CashSubmission.objects.select_for_update().filter(deposit=deposit).order_by("pk")
    )
    collections = lock_collections(deposit.collections.all())

    now = timezone.now()
    deposit.failure_reason = reason
    deposit.failed_at = now
    deposit.failed_by = actor
    deposit.save(update_fields=["status", "failure_reason", "failed_at", "failed_by", "updated_at"])
    CashSubmission.objects.filter(pk__in=[s.pk for s in submissions]).update(
        deposit=None, updated_at=now
    )
    move_collections(
        collections, Collection.Status.BRANCH_RECEIVED, deposit=None, deposited_at=None
    )

    # The submissions are detached so the cash can be redeposited; the trail keeps the link.
    log_event(
        actor,
        AuditAction.DEPOSIT_FAILED,
        deposit,
        before=before,
        after={
            **snapshot(deposit, ["status", "failure_reason"]),
            "released_submission_ids": [s.pk for s in submissions],
            "released_collection_ids": [c.pk for c in collections],
        },
    )
    # The redeposit is checked afresh, so a mismatch on this attempt no longer stands.
    for discrepancy in deposit.discrepancies.filter(status=Discrepancy.Status.OPEN).order_by("pk"):
        resolve_discrepancy(
            actor,
            discrepancy,
            outcome=Discrepancy.Status.RESOLVED,
            resolution_notes=f"Deposit failed: {reason}",
        )
    return deposit


def _require_checker(actor: User, deposit: BankDeposit) -> None:
    """Whoever records a deposit cannot also confirm its outcome."""
    if deposit.created_by_id == actor.pk:
        raise ScopeViolation(
            "The person who recorded a deposit cannot confirm its settlement.",
            details={"deposit_number": deposit.deposit_number},
        )


# Gateway settlements ----------------------------------------------------------------------


@transaction.atomic
def record_gateway_settlement(
    actor: User,
    *,
    collection_ids: Iterable[int] | None = None,
    up_to_date: date | None = None,
    gross_amount: Decimal,
    fee_amount: Decimal,
    tax_amount: Decimal,
    net_amount: Decimal,
    utr: str,
    settled_on: date,
    remarks: str = "",
    idempotency_key: uuid.UUID,
) -> tuple[BankDeposit, bool]:
    """Settle captured UPI collections from a gateway settlement report (net of fee and tax)."""
    _require_role(actor, User.Role.ADMIN, User.Role.FINANCE)
    if collection_ids is not None:
        collection_ids = sorted(set(collection_ids))
    gross_amount, fee_amount, tax_amount, net_amount = (
        to_money(amount) for amount in (gross_amount, fee_amount, tax_amount, net_amount)
    )
    reference = normalize_reference(utr)
    remarks = remarks.strip()

    lock_idempotency_key(IDEMPOTENCY_SCOPE, actor.pk, idempotency_key)
    existing = BankDeposit.objects.filter(created_by=actor, idempotency_key=idempotency_key).first()
    if existing is not None:
        amounts = (gross_amount, fee_amount, tax_amount, net_amount)
        replay = (
            existing.source == BankDeposit.Source.GATEWAY
            and existing.reference_number == reference
            and existing.settled_on == settled_on
            and (
                existing.deposited_amount,
                existing.fee_amount,
                existing.tax_amount,
                existing.settled_amount,
            )
            == amounts
            and selectors.settlement_selection(existing) == (collection_ids, up_to_date)
        )
        if not replay:
            raise IdempotencyConflict(details={"deposit_number": existing.deposit_number})
        return existing, False

    if (collection_ids is None) == (up_to_date is None):
        raise ValidationFailed("Provide either collection_ids or up_to_date.")
    if not reference:
        raise ValidationFailed("The settlement UTR is required.")
    _require_not_future(settled_on, "settled_on")
    if gross_amount - fee_amount - tax_amount != net_amount:
        raise ValidationFailed(
            "The net amount must equal the gross amount less fee and tax.",
            details={
                "gross_amount": str(gross_amount),
                "fee_amount": str(fee_amount),
                "tax_amount": str(tax_amount),
                "net_amount": str(net_amount),
            },
        )

    account = BankAccount.objects.filter(is_gateway=True, is_active=True).first()
    if account is None:
        raise ValidationFailed("No active gateway settlement account is configured.")
    collections = _lock_unsettled_upi_collections(collection_ids, up_to_date)
    latest_payment = business_date(max(c.collected_at for c in collections))
    if settled_on < latest_payment:
        raise ValidationFailed(
            "A settlement cannot be dated before the payments it covers.",
            details={"settled_on": settled_on, "latest_payment_date": latest_payment},
        )

    expected_amount = sum((c.amount for c in collections), ZERO)
    shortfall = expected_amount - fee_amount - tax_amount - net_amount
    if shortfall and not remarks:
        raise ValidationFailed(
            "Remarks are required when the settlement does not match the captured payments.",
            details={
                "expected_amount": str(expected_amount),
                "expected_net_amount": str(expected_amount - fee_amount - tax_amount),
                "net_amount": str(net_amount),
                "difference": str(shortfall),
            },
        )
    _ensure_unused_reference(account, reference)

    now = timezone.now()
    status = BankDeposit.Status.SETTLED_WITH_MISMATCH if shortfall else BankDeposit.Status.SETTLED
    settlement = BankDeposit.objects.create(
        deposit_number=deposit_number(GATEWAY_SCOPE),
        source=BankDeposit.Source.GATEWAY,
        bank_account=account,
        reference_number=reference,
        deposit_date=settled_on,
        expected_amount=expected_amount,
        deposited_amount=gross_amount,
        fee_amount=fee_amount,
        tax_amount=tax_amount,
        settled_amount=net_amount,
        settled_on=settled_on,
        settlement_reference=reference,
        status=status,
        remarks=remarks,
        settled_at=now,
        settled_by=actor,
        created_by=actor,
        idempotency_key=idempotency_key,
    )
    move_collections(collections, Collection.Status.SETTLED, deposit=settlement, settled_at=now)

    log_event(
        actor,
        AuditAction.GATEWAY_SETTLEMENT_RECORDED,
        settlement,
        after={
            **snapshot(settlement, DEPOSIT_AUDIT_FIELDS),
            "collection_ids": [c.pk for c in collections],
            "requested": {"collection_ids": collection_ids, "up_to_date": up_to_date},
        },
    )
    if shortfall:
        _raise_discrepancy(
            actor,
            settlement,
            kind=Discrepancy.Kind.GATEWAY_MISMATCH,
            shortfall=shortfall,
            reason_code=Discrepancy.ReasonCode.OTHER,
            notes=remarks,
        )
    return settlement, True


def _lock_unsettled_upi_collections(
    collection_ids: Iterable[int] | None, up_to_date: date | None
) -> list[Collection]:
    unsettled = Collection.objects.filter(
        mode=Collection.Mode.UPI, status=Collection.Status.COLLECTED
    )
    if up_to_date is not None:
        _require_not_future(up_to_date, "up_to_date")
        unsettled = unsettled.filter(collected_at__lt=day_bounds(up_to_date)[1])
        count = unsettled.count()
        if count > MAX_SETTLEMENT_ITEMS:
            raise ValidationFailed(
                f"A settlement can cover at most {MAX_SETTLEMENT_ITEMS} payments; "
                "settle an earlier date first.",
                details={"up_to_date": up_to_date, "unsettled_count": count},
            )
        collections = lock_collections(unsettled)
        if not collections:
            raise ValidationFailed(
                "There are no unsettled UPI collections up to this date.",
                details={"up_to_date": up_to_date},
            )
        return collections

    ids = collection_ids or []
    if not ids:
        raise ValidationFailed("Select at least one UPI collection to settle.")
    collections = lock_collections(Collection.objects.filter(pk__in=ids))
    missing = sorted(set(ids) - {c.pk for c in collections})
    if missing:
        raise ResourceNotFound("Collection not found.", details={"collection_ids": missing})
    ineligible = [
        c.pk
        for c in collections
        if c.mode != Collection.Mode.UPI or c.status != Collection.Status.COLLECTED
    ]
    if ineligible:
        raise ValidationFailed(
            "Only captured, unsettled UPI collections can be settled through the gateway.",
            details={"collection_ids": ineligible},
        )
    return collections


# Delayed settlements ----------------------------------------------------------------------


@transaction.atomic
def flag_delayed_settlements(today: date | None = None) -> list[BankDeposit]:
    """Audit every deposit pending beyond the SLA, at most once per deposit per day."""
    today = today or business_date()
    start, end = day_bounds(today)
    already_flagged = set(
        AuditLog.objects.filter(
            action=AuditAction.DEPOSIT_SETTLEMENT_DELAYED,
            entity_type=BankDeposit._meta.model_name,
            created_at__gte=start,
            created_at__lt=end,
        ).values_list("entity_id", flat=True)
    )
    flagged = []
    for deposit in BankDeposit.objects.delayed(today=today).select_related("branch"):
        if str(deposit.pk) in already_flagged:
            continue
        days_pending = (today - deposit.deposit_date).days
        log_event(
            None,
            AuditAction.DEPOSIT_SETTLEMENT_DELAYED,
            deposit,
            after={
                "deposit_number": deposit.deposit_number,
                "deposit_date": deposit.deposit_date,
                "days_pending": days_pending,
                "deposited_amount": deposit.deposited_amount,
            },
        )
        logger.warning(
            "Settlement delayed: %s (%s) pending %d days since %s",
            deposit.deposit_number,
            deposit.branch.code if deposit.branch else GATEWAY_SCOPE,
            days_pending,
            deposit.deposit_date.isoformat(),
        )
        flagged.append(deposit)
    return flagged
