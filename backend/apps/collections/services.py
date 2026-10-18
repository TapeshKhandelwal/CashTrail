"""Recording and voiding repayments.

Every write locks the loan row first, so collections against one loan are
serialized and the outstanding balance can never be overrun by concurrent requests.
"""

import uuid
from collections.abc import Sequence
from datetime import datetime, timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from apps.audit.models import AuditAction
from apps.audit.services import log_event, snapshot
from apps.core.dates import business_date
from apps.core.exceptions import (
    IdempotencyConflict,
    OverCollection,
    PossibleDuplicate,
    ScopeViolation,
    ValidationFailed,
)
from apps.core.money import ZERO, to_money
from apps.core.numbering import receipt_number
from apps.customers.models import Customer
from apps.loans.models import Installment, Loan
from apps.payments import selectors as payment_selectors

from .models import Allocation, Collection

AUDIT_FIELDS = (
    "receipt_number",
    "loan",
    "agent",
    "amount",
    "balance_after",
    "mode",
    "status",
    "collected_at",
    "gateway_payment_id",
)
LOAN_AUDIT_FIELDS = ("status", "amount_paid", "closed_at")


def record_collection(
    *,
    actor,
    loan: Loan,
    amount: Decimal | str | int,
    mode: str,
    idempotency_key: uuid.UUID | None,
    gateway_payment_id: str | None = None,
    confirm_duplicate: bool = False,
    remarks: str = "",
    collected_at: datetime | None = None,
) -> tuple[Collection, bool]:
    """Record a repayment and apply it to the oldest unpaid installments.

    Returns `(collection, replayed)`: `replayed` is true when an earlier request with the
    same idempotency key (cash) or gateway payment id (UPI) already recorded it.
    """
    amount = _clean_amount(amount)
    gateway_payment_id = (gateway_payment_id or "").strip()
    _check_mode(mode, idempotency_key, gateway_payment_id)
    collected_at = _clean_collected_at(collected_at)

    with transaction.atomic():
        loan = _lock_loan(loan)
        # Checked under the loan lock so a retry racing the original sees its committed row.
        existing = _find_existing(actor, idempotency_key, gateway_payment_id)
        if existing is not None:
            return _replayed(existing, loan, amount, mode), True

        check_can_collect(actor, loan)
        # Open UPI orders hold back their amount: the customer may still complete them.
        _check_within_balance(loan, amount, reserved=payment_selectors.reserved_amount(loan))
        if mode == Collection.Mode.CASH and not confirm_duplicate:
            _check_possible_duplicate(actor, loan, amount, collected_at)

        collection = _record(
            actor,
            loan,
            amount=amount,
            mode=mode,
            collected_at=collected_at,
            idempotency_key=idempotency_key,
            gateway_payment_id=gateway_payment_id,
            remarks=remarks,
        )
    return collection, False


def record_gateway_payment(
    *,
    agent,
    loan: Loan,
    amount: Decimal,
    gateway_payment_id: str,
    collected_at: datetime | None = None,
    remarks: str = "",
) -> tuple[Collection, bool]:
    """Record a UPI payment the gateway captured on an order `agent` raised.

    The assignment, customer and loan checks ran when the order was raised; money already
    received is not refused because one of them changed since. Raises `OverCollection`
    when the balance can no longer absorb the payment, which then has to be refunded.
    """
    amount = _clean_amount(amount)
    gateway_payment_id = gateway_payment_id.strip()
    _check_mode(Collection.Mode.UPI, None, gateway_payment_id)
    collected_at = _clean_collected_at(collected_at)

    with transaction.atomic():
        loan = _lock_loan(loan)
        existing = _find_existing(agent, None, gateway_payment_id)
        if existing is not None:
            return _replayed(existing, loan, amount, Collection.Mode.UPI), True
        _check_within_balance(loan, amount)
        collection = _record(
            agent,
            loan,
            amount=amount,
            mode=Collection.Mode.UPI,
            collected_at=collected_at,
            idempotency_key=None,
            gateway_payment_id=gateway_payment_id,
            remarks=remarks,
        )
    return collection, False


def void_collection(*, actor, collection: Collection, reason: str) -> Collection:
    """Cancel a cash receipt the agent still holds, reversing its effect on the loan."""
    reason = (reason or "").strip()
    if not reason:
        raise ValidationFailed("A reason is required to void a collection.")

    with transaction.atomic():
        loan = Loan.objects.select_for_update().get(pk=collection.loan_id)
        collection = Collection.objects.select_for_update().get(pk=collection.pk)
        if collection.agent_id != actor.pk:
            raise ScopeViolation("Only the agent who recorded a collection can void it.")
        # Locked so a concurrent deactivation either sees the reopened loan or blocks the void.
        customer = Customer.objects.select_for_update().get(pk=loan.customer_id)
        if not customer.is_active:
            raise ValidationFailed(
                "The customer is inactive; reactivate them before voiding their receipt.",
                code="CUSTOMER_INACTIVE",
                details={"customer": customer.customer_code},
            )

        before = snapshot(collection, ("status", "voided_at", "void_reason"))
        collection.transition_to(Collection.Status.VOIDED)
        now = timezone.now()
        collection.voided_at = now
        collection.void_reason = reason
        collection.voided_by = actor
        collection.save(
            update_fields=["status", "voided_at", "void_reason", "voided_by", "updated_at"]
        )

        collection.allocations.filter(reversed_at__isnull=True).update(
            reversed_at=now, updated_at=now
        )
        _reallocate(loan, at=now)
        _apply_to_loan(actor, loan, -collection.amount)

        log_event(
            actor,
            AuditAction.COLLECTION_VOIDED,
            collection,
            before=before,
            after=snapshot(collection, ("status", "voided_at", "void_reason")),
        )
    return collection


def lock_collections(collections: QuerySet[Collection]) -> list[Collection]:
    return list(collections.select_for_update().order_by("pk"))


def move_collections(collections: Sequence[Collection], target: str, **changes) -> list[int]:
    """Move already-locked receipts one lifecycle step, validating each, in a single UPDATE."""
    for collection in collections:
        collection.transition_to(target)
    ids = [collection.pk for collection in collections]
    if ids:
        Collection.objects.filter(pk__in=ids).update(
            status=target, updated_at=timezone.now(), **changes
        )
    return ids


def _clean_amount(value) -> Decimal:
    try:
        amount = to_money(value)
    except (TypeError, ValueError) as exc:
        raise ValidationFailed("Amount must be a decimal number.") from exc
    if amount != Decimal(str(value)):
        raise ValidationFailed("Amount can have at most two decimal places.")
    if amount <= ZERO:
        raise ValidationFailed("Amount must be greater than zero.")
    return amount


def _clean_collected_at(collected_at: datetime | None) -> datetime:
    now = timezone.now()
    if collected_at is not None and collected_at > now:
        raise ValidationFailed("A repayment cannot be dated in the future.")
    return collected_at or now


def _lock_loan(loan: Loan) -> Loan:
    return (
        Loan.objects.select_for_update(of=("self",))
        .select_related("customer", "branch")
        .get(pk=loan.pk)
    )


def _replayed(existing: Collection, loan: Loan, amount: Decimal, mode: str) -> Collection:
    if (existing.loan_id, existing.amount, existing.mode) != (loan.pk, amount, mode):
        raise IdempotencyConflict(details={"receipt_number": existing.receipt_number})
    return existing


def _check_within_balance(loan: Loan, amount: Decimal, *, reserved: Decimal = ZERO) -> None:
    if amount <= loan.outstanding - reserved:
        return
    details = {"outstanding": str(loan.outstanding), "amount": str(amount)}
    if reserved:
        raise OverCollection(
            "The amount exceeds the outstanding balance not already awaiting UPI payment.",
            details={**details, "awaiting_payment": str(reserved)},
        )
    raise OverCollection(
        f"The amount exceeds the outstanding balance of {loan.outstanding}.", details=details
    )


def _record(
    actor,
    loan: Loan,
    *,
    amount: Decimal,
    mode: str,
    collected_at: datetime,
    idempotency_key: uuid.UUID | None,
    gateway_payment_id: str,
    remarks: str,
) -> Collection:
    collection = Collection.objects.create(
        receipt_number=receipt_number(loan.branch.code, on=business_date(collected_at)),
        loan=loan,
        customer=loan.customer,
        branch=loan.branch,
        agent=actor,
        amount=amount,
        # Kept as recorded: later payments and voids do not rewrite a receipt's balance.
        balance_after=loan.outstanding - amount,
        mode=mode,
        collected_at=collected_at,
        idempotency_key=idempotency_key,
        gateway_payment_id=gateway_payment_id,
        remarks=remarks.strip(),
    )
    allocations = _allocate(collection, loan, at=collected_at)
    _apply_to_loan(actor, loan, amount)
    log_event(
        actor,
        AuditAction.COLLECTION_RECORDED,
        collection,
        after={
            **snapshot(collection, AUDIT_FIELDS),
            "allocations": [
                {"installment": a.installment_id, "amount": a.amount} for a in allocations
            ],
        },
    )
    return collection


def _check_mode(mode: str, idempotency_key, gateway_payment_id: str) -> None:
    if mode == Collection.Mode.CASH:
        if idempotency_key is None:
            raise ValidationFailed("Cash collections require an idempotency key.")
        if gateway_payment_id:
            raise ValidationFailed("Cash collections cannot carry a gateway payment id.")
    elif mode == Collection.Mode.UPI:
        if not gateway_payment_id:
            raise ValidationFailed("UPI collections require the gateway payment id.")
    else:
        raise ValidationFailed(f"Unsupported payment mode: {mode}.")


def _find_existing(actor, idempotency_key, gateway_payment_id: str) -> Collection | None:
    if gateway_payment_id:
        lookup = {"gateway_payment_id": gateway_payment_id}
    elif idempotency_key is not None:
        lookup = {"agent": actor, "idempotency_key": idempotency_key}
    else:
        return None
    return Collection.objects.filter(**lookup).first()


def check_can_collect(actor, loan: Loan) -> None:
    """Shared by cash collection and UPI orders: the assigned agent, an active customer and loan."""
    if not actor.is_agent or loan.customer.assigned_agent_id != actor.pk:
        raise ScopeViolation("Only the agent assigned to this customer can record repayments.")
    if not loan.customer.is_active:
        raise ValidationFailed(
            "The customer is inactive.",
            code="CUSTOMER_INACTIVE",
            details={"customer": loan.customer.customer_code},
        )
    if loan.status != Loan.Status.ACTIVE:
        raise ValidationFailed(
            "The loan is not active.",
            code="LOAN_NOT_ACTIVE",
            details={"loan": loan.loan_number, "status": loan.status},
        )


def _check_possible_duplicate(actor, loan: Loan, amount: Decimal, at: datetime) -> None:
    window = timedelta(minutes=settings.DUPLICATE_WINDOW_MINUTES)
    recent = (
        Collection.objects.filter(
            loan=loan,
            agent=actor,
            amount=amount,
            collected_at__gte=at - window,
            collected_at__lte=at + window,
        )
        .exclude(status=Collection.Status.VOIDED)
        .order_by("-collected_at")
        .first()
    )
    if recent is not None:
        raise PossibleDuplicate(
            f"{recent.receipt_number} for the same amount was recorded on this loan moments ago. "
            "Confirm to record another.",
            details={
                "collection_id": recent.pk,
                "receipt_number": recent.receipt_number,
                "amount": str(recent.amount),
                "collected_at": recent.collected_at.isoformat(),
            },
        )


def _allocate(collection: Collection, loan: Loan, *, at: datetime) -> list[Allocation]:
    """Waterfall the amount over unpaid installments, oldest first."""
    remaining = collection.amount
    allocations = []
    unpaid = (
        Installment.objects.select_for_update()
        .filter(loan=loan)
        .exclude(status=Installment.Status.PAID)
        .order_by("installment_no")
    )
    for installment in unpaid:
        if remaining == ZERO:
            break
        portion = min(remaining, installment.outstanding)
        installment.amount_paid += portion
        installment.sync_status(at=at)
        installment.save(update_fields=["amount_paid", "status", "paid_at", "updated_at"])
        allocations.append(
            Allocation(collection=collection, installment=installment, amount=portion)
        )
        remaining -= portion
    return Allocation.objects.bulk_create(allocations)


def _reallocate(loan: Loan, *, at: datetime) -> None:
    """Re-run the oldest-first waterfall over the loan's remaining receipts after a void.

    Receipts recorded after the voided one move forward into the installments it had
    covered. Allocation rows are immutable, so a receipt whose split changes has its rows
    reversed and new ones written.
    """
    installments = list(
        Installment.objects.select_for_update().filter(loan=loan).order_by("installment_no")
    )
    effective = Allocation.objects.filter(installment__loan=loan, reversed_at__isnull=True)
    current: dict[int, dict[int, Decimal]] = {}
    for collection_id, installment_id, amount in effective.values_list(
        "collection_id", "installment_id", "amount"
    ):
        current.setdefault(collection_id, {})[installment_id] = amount

    unpaid = {installment.pk: installment.amount_due for installment in installments}
    superseded, replacements = [], []
    # Receipts were applied in the order they were recorded, which is primary-key order.
    for collection in Collection.objects.filter(pk__in=list(current)).order_by("pk"):
        split, remaining = {}, collection.amount
        for installment in installments:
            portion = min(remaining, unpaid[installment.pk])
            if portion:
                split[installment.pk] = portion
                unpaid[installment.pk] -= portion
                remaining -= portion
        if split != current[collection.pk]:
            superseded.append(collection.pk)
            replacements += [
                Allocation(collection=collection, installment_id=pk, amount=amount)
                for pk, amount in split.items()
            ]
    if superseded:
        effective.filter(collection__in=superseded).update(reversed_at=at, updated_at=at)
        Allocation.objects.bulk_create(replacements)

    for installment in installments:
        paid = installment.amount_due - unpaid[installment.pk]
        if paid != installment.amount_paid:
            installment.amount_paid = paid
            installment.sync_status(at=at)
            installment.save(update_fields=["amount_paid", "status", "paid_at", "updated_at"])


def _apply_to_loan(actor, loan: Loan, delta: Decimal) -> None:
    """Move `loan.amount_paid` by `delta`, closing or reopening the loan as the balance demands."""
    before = snapshot(loan, LOAN_AUDIT_FIELDS)
    loan.amount_paid += delta
    action = None
    if loan.outstanding == ZERO and loan.status == Loan.Status.ACTIVE:
        loan.transition_to(Loan.Status.CLOSED)
        loan.closed_at = timezone.now()
        action = AuditAction.LOAN_CLOSED
    elif loan.outstanding > ZERO and loan.status == Loan.Status.CLOSED:
        loan.transition_to(Loan.Status.ACTIVE)
        loan.closed_at = None
        action = AuditAction.LOAN_REOPENED
    loan.save(update_fields=["amount_paid", "status", "closed_at", "updated_at"])
    if action is not None:
        log_event(actor, action, loan, before=before, after=snapshot(loan, LOAN_AUDIT_FIELDS))
