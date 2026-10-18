from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.models import StateMachineMixin, TimeStampedModel, money_field


class Collection(StateMachineMixin, TimeStampedModel):
    """One repayment received from a customer; one receipt."""

    class Mode(models.TextChoices):
        CASH = "CASH", "Cash"
        UPI = "UPI", "UPI"

    class Status(models.TextChoices):
        COLLECTED = "COLLECTED", "Collected"
        SUBMITTED = "SUBMITTED", "Submitted to branch"
        BRANCH_RECEIVED = "BRANCH_RECEIVED", "Received at branch"
        DEPOSITED = "DEPOSITED", "Deposited in bank"
        SETTLED = "SETTLED", "Settled"
        VOIDED = "VOIDED", "Voided"

    CASH_TRANSITIONS = {
        Status.COLLECTED: frozenset({Status.SUBMITTED, Status.VOIDED}),
        Status.SUBMITTED: frozenset({Status.COLLECTED, Status.BRANCH_RECEIVED}),
        Status.BRANCH_RECEIVED: frozenset({Status.DEPOSITED}),
        Status.DEPOSITED: frozenset({Status.BRANCH_RECEIVED, Status.SETTLED}),
    }
    # Gateway payments never pass through an agent's hands or a branch.
    UPI_TRANSITIONS = {Status.COLLECTED: frozenset({Status.SETTLED})}

    receipt_number = models.CharField(max_length=32, unique=True)
    # Single-column FK indexes are left out where a composite index leads with the column.
    loan = models.ForeignKey(
        "loans.Loan", on_delete=models.PROTECT, related_name="collections", db_index=False
    )
    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.PROTECT, related_name="collections"
    )
    branch = models.ForeignKey(
        "branches.Branch", on_delete=models.PROTECT, related_name="collections", db_index=False
    )
    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="collections",
        db_index=False,
    )
    amount = money_field()
    balance_after = money_field(
        null=True,
        blank=True,
        help_text="Loan balance right after this receipt was applied; never changes afterwards.",
    )
    mode = models.CharField(max_length=10, choices=Mode.choices, default=Mode.CASH)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.COLLECTED)
    collected_at = models.DateTimeField(default=timezone.now)
    submitted_at = models.DateTimeField(null=True, blank=True)
    branch_received_at = models.DateTimeField(null=True, blank=True)
    deposited_at = models.DateTimeField(null=True, blank=True)
    settled_at = models.DateTimeField(null=True, blank=True)
    submission = models.ForeignKey(
        "reconciliation.CashSubmission",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="collections",
    )
    deposit = models.ForeignKey(
        "deposits.BankDeposit",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="collections",
    )
    idempotency_key = models.UUIDField(null=True, blank=True)
    gateway_payment_id = models.CharField(max_length=64, blank=True)
    remarks = models.TextField(blank=True)
    voided_at = models.DateTimeField(null=True, blank=True)
    void_reason = models.TextField(blank=True)
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        ordering = ["-collected_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["agent", "idempotency_key"], name="uniq_collection_agent_idempotency_key"
            ),
            models.UniqueConstraint(
                fields=["gateway_payment_id"],
                condition=~Q(gateway_payment_id=""),
                name="uniq_collection_gateway_payment_id",
            ),
            models.CheckConstraint(condition=Q(amount__gt=0), name="collection_amount_positive"),
            models.CheckConstraint(
                condition=Q(mode="CASH", agent__isnull=False, gateway_payment_id="")
                | (Q(mode="UPI") & ~Q(gateway_payment_id="")),
                name="collection_mode_consistency",
            ),
            models.CheckConstraint(
                condition=~Q(mode="UPI", status__in=["SUBMITTED", "BRANCH_RECEIVED", "DEPOSITED"]),
                name="collection_upi_skips_branch_states",
            ),
            models.CheckConstraint(
                condition=~Q(
                    mode="CASH", status__in=["SUBMITTED", "BRANCH_RECEIVED", "DEPOSITED", "SETTLED"]
                )
                | Q(submission__isnull=False),
                name="collection_cash_in_branch_has_submission",
            ),
            models.CheckConstraint(
                condition=~Q(status__in=["DEPOSITED", "SETTLED"]) | Q(deposit__isnull=False),
                name="collection_deposited_has_deposit",
            ),
            models.CheckConstraint(
                condition=Q(status="VOIDED", voided_at__isnull=False)
                | (~Q(status="VOIDED") & Q(voided_at__isnull=True)),
                name="collection_void_consistency",
            ),
        ]
        indexes = [
            models.Index(fields=["branch", "collected_at"], name="collection_branch_time_idx"),
            models.Index(fields=["agent", "status"], name="collection_agent_status_idx"),
            models.Index(fields=["status", "collected_at"], name="collection_status_time_idx"),
            models.Index(fields=["loan", "collected_at"], name="collection_loan_time_idx"),
            models.Index(
                fields=["agent"],
                condition=Q(mode="CASH", status__in=["COLLECTED", "SUBMITTED"]),
                name="collection_cash_held_idx",
            ),
        ]

    def __str__(self):
        return self.receipt_number

    def allowed_transitions(self) -> frozenset[str]:
        transitions = self.UPI_TRANSITIONS if self.mode == self.Mode.UPI else self.CASH_TRANSITIONS
        return transitions.get(self.status, frozenset())

    @property
    def is_locked(self) -> bool:
        """Financial fields freeze once cash leaves the agent (a DB trigger enforces it too)."""
        return self.status != self.Status.COLLECTED


class Allocation(TimeStampedModel):
    """How much of a collection was applied to which installment (oldest first)."""

    collection = models.ForeignKey(Collection, on_delete=models.PROTECT, related_name="allocations")
    installment = models.ForeignKey(
        "loans.Installment", on_delete=models.PROTECT, related_name="allocations"
    )
    amount = money_field()
    reversed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=(
            "Set when the collection is voided or its split is re-applied after another "
            "receipt is voided; rows are never deleted."
        ),
    )

    class Meta:
        ordering = ["collection_id", "installment__installment_no"]
        constraints = [
            models.UniqueConstraint(
                fields=["collection", "installment"],
                condition=Q(reversed_at__isnull=True),
                name="uniq_allocation_collection_installment",
            ),
            models.CheckConstraint(condition=Q(amount__gt=0), name="allocation_amount_positive"),
        ]

    def __str__(self):
        return f"{self.collection_id} → {self.installment_id}: {self.amount}"
