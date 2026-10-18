from django.conf import settings
from django.db import models
from django.db.models import F, Func, IntegerField, Q
from django.db.models.lookups import Exact
from django.utils import timezone

from apps.core.models import StateMachineMixin, TimeStampedModel, money_field


class CashSubmission(StateMachineMixin, TimeStampedModel):
    """An agent handing over a batch of cash receipts to the branch."""

    class Status(models.TextChoices):
        SUBMITTED = "SUBMITTED", "Awaiting review"
        APPROVED = "APPROVED", "Approved"
        APPROVED_WITH_DISCREPANCY = "APPROVED_WITH_DISCREPANCY", "Approved with discrepancy"
        REJECTED = "REJECTED", "Rejected"

    APPROVED_STATUSES = frozenset({Status.APPROVED, Status.APPROVED_WITH_DISCREPANCY})
    TRANSITIONS = {
        Status.SUBMITTED: frozenset(
            {Status.APPROVED, Status.APPROVED_WITH_DISCREPANCY, Status.REJECTED}
        ),
    }

    submission_number = models.CharField(max_length=32, unique=True)
    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="cash_submissions",
        db_index=False,
    )
    branch = models.ForeignKey(
        "branches.Branch", on_delete=models.PROTECT, related_name="cash_submissions", db_index=False
    )
    expected_amount = money_field(help_text="Server-computed sum of the included cash receipts.")
    declared_amount = money_field(help_text="What the agent says they are handing over.")
    received_amount = money_field(null=True, blank=True, help_text="Counted by the branch manager.")
    difference = models.GeneratedField(
        expression=F("expected_amount") - F("received_amount"),
        output_field=models.DecimalField(max_digits=14, decimal_places=2),
        db_persist=True,
        help_text="Positive = shortage, negative = excess.",
    )
    denominations = models.JSONField(
        null=True,
        blank=True,
        help_text='The agent\'s own count, e.g. {"500": 90, "200": 10}; null when the cash was '
        "handed over as receipted without counting.",
    )
    received_denominations = models.JSONField(
        null=True, blank=True, help_text="The branch manager's count, when it was itemised."
    )
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.SUBMITTED)
    submitted_at = models.DateTimeField(default=timezone.now)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reviewed_submissions",
    )
    review_remarks = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)
    deposit = models.ForeignKey(
        "deposits.BankDeposit",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="submissions",
    )
    idempotency_key = models.UUIDField()

    class Meta:
        ordering = ["-submitted_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["agent", "idempotency_key"], name="uniq_submission_agent_idempotency_key"
            ),
            models.UniqueConstraint(
                fields=["agent"],
                condition=Q(status="SUBMITTED"),
                name="uniq_submission_pending_per_agent",
            ),
            models.CheckConstraint(
                condition=Q(expected_amount__gt=0), name="submission_expected_positive"
            ),
            models.CheckConstraint(
                condition=Q(declared_amount__gte=0), name="submission_declared_non_negative"
            ),
            models.CheckConstraint(
                condition=Q(received_amount__isnull=True) | Q(received_amount__gte=0),
                name="submission_received_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(
                    status="SUBMITTED", reviewed_at__isnull=True, received_amount__isnull=True
                )
                | Q(
                    status="APPROVED",
                    reviewed_at__isnull=False,
                    received_amount__isnull=False,
                    received_amount=F("expected_amount"),
                )
                | (
                    Q(status="APPROVED_WITH_DISCREPANCY", reviewed_at__isnull=False)
                    & Q(received_amount__isnull=False)
                    & ~Q(received_amount=F("expected_amount"))
                )
                | (Q(status="REJECTED", reviewed_at__isnull=False) & ~Q(rejection_reason="")),
                name="submission_review_consistency",
            ),
            models.CheckConstraint(
                condition=Q(deposit__isnull=True)
                | Q(status__in=["APPROVED", "APPROVED_WITH_DISCREPANCY"]),
                name="submission_deposit_requires_approval",
            ),
        ]
        indexes = [
            models.Index(
                fields=["branch", "status", "submitted_at"], name="submission_branch_queue_idx"
            ),
            models.Index(
                fields=["branch"],
                condition=Q(
                    status__in=["APPROVED", "APPROVED_WITH_DISCREPANCY"], deposit__isnull=True
                ),
                name="submission_undeposited_idx",
            ),
        ]

    def __str__(self):
        return self.submission_number

    @property
    def is_locked(self) -> bool:
        return self.status != self.Status.SUBMITTED

    @property
    def is_approved(self) -> bool:
        return self.status in self.APPROVED_STATUSES


class SubmissionItem(models.Model):
    """A receipt handed over in a submission. Kept when a rejection returns the receipt to
    the agent, so what each hand-over contained stays queryable (rows are immutable)."""

    submission = models.ForeignKey(
        CashSubmission, on_delete=models.PROTECT, related_name="items", db_index=False
    )
    collection = models.ForeignKey(
        "collections.Collection", on_delete=models.PROTECT, related_name="submission_items"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["submission", "collection"], name="uniq_submission_item"
            ),
        ]

    def __str__(self):
        return f"{self.submission_id} ← {self.collection_id}"


class Discrepancy(StateMachineMixin, TimeStampedModel):
    """A difference found at a checkpoint; tracked and resolved without touching the receipts."""

    class Kind(models.TextChoices):
        CASH_SHORTAGE = "CASH_SHORTAGE", "Cash shortage"
        CASH_EXCESS = "CASH_EXCESS", "Cash excess"
        DEPOSIT_MISMATCH = "DEPOSIT_MISMATCH", "Deposit mismatch"
        SETTLEMENT_MISMATCH = "SETTLEMENT_MISMATCH", "Settlement mismatch"
        GATEWAY_MISMATCH = "GATEWAY_MISMATCH", "Gateway settlement mismatch"

    class Direction(models.TextChoices):
        SHORT = "SHORT", "Short"
        EXCESS = "EXCESS", "Excess"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        RESOLVED = "RESOLVED", "Resolved"
        WRITTEN_OFF = "WRITTEN_OFF", "Written off"

    class ReasonCode(models.TextChoices):
        COUNTING_ERROR = "COUNTING_ERROR", "Counting error"
        AGENT_SHORTAGE = "AGENT_SHORTAGE", "Agent shortage"
        BANK_CHARGES = "BANK_CHARGES", "Bank charges"
        BANK_ERROR = "BANK_ERROR", "Bank error"
        OTHER = "OTHER", "Other"

    CASH_KINDS = frozenset({Kind.CASH_SHORTAGE, Kind.CASH_EXCESS})
    TRANSITIONS = {Status.OPEN: frozenset({Status.RESOLVED, Status.WRITTEN_OFF})}

    kind = models.CharField(max_length=30, choices=Kind.choices)
    direction = models.CharField(max_length=10, choices=Direction.choices)
    amount = money_field(help_text="Absolute difference.")
    submission = models.ForeignKey(
        CashSubmission,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="discrepancies",
    )
    deposit = models.ForeignKey(
        "deposits.BankDeposit",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="discrepancies",
    )
    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="discrepancies",
    )
    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="discrepancies",
        help_text="Responsible agent for cash discrepancies.",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    reason_code = models.CharField(max_length=20, choices=ReasonCode.choices)
    notes = models.TextField(blank=True)
    resolution_notes = models.TextField(blank=True)
    raised_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "discrepancies"
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="discrepancy_amount_positive"),
            models.CheckConstraint(
                condition=Exact(
                    Func(
                        F("submission"),
                        F("deposit"),
                        function="num_nonnulls",
                        output_field=IntegerField(),
                    ),
                    1,
                ),
                name="discrepancy_single_source",
            ),
            models.CheckConstraint(
                condition=Q(kind__in=["CASH_SHORTAGE", "CASH_EXCESS"], submission__isnull=False)
                | (~Q(kind__in=["CASH_SHORTAGE", "CASH_EXCESS"]) & Q(deposit__isnull=False)),
                name="discrepancy_kind_matches_source",
            ),
            models.CheckConstraint(
                condition=~Q(kind="CASH_SHORTAGE", direction="EXCESS")
                & ~Q(kind="CASH_EXCESS", direction="SHORT"),
                name="discrepancy_cash_direction_matches_kind",
            ),
            models.CheckConstraint(
                condition=Q(status="OPEN", resolved_at__isnull=True)
                | (
                    Q(status__in=["RESOLVED", "WRITTEN_OFF"], resolved_at__isnull=False)
                    & ~Q(resolution_notes="")
                ),
                name="discrepancy_resolution_consistency",
            ),
        ]
        indexes = [
            models.Index(
                fields=["branch", "kind"],
                condition=Q(status="OPEN"),
                name="discrepancy_open_idx",
            ),
            models.Index(fields=["status", "created_at"], name="discrepancy_status_time_idx"),
        ]

    def __str__(self):
        return f"{self.get_kind_display()} ₹{self.amount}"

    @property
    def is_cash(self) -> bool:
        return self.kind in self.CASH_KINDS
