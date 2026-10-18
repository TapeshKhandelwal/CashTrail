from datetime import datetime
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from apps.core.dates import business_date
from apps.core.models import StateMachineMixin, TimeStampedModel, money_field
from apps.core.money import ZERO


class Loan(StateMachineMixin, TimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        CLOSED = "CLOSED", "Closed"

    TRANSITIONS = {
        Status.ACTIVE: frozenset({Status.CLOSED}),
        # A voided collection can reopen a loan that it had closed.
        Status.CLOSED: frozenset({Status.ACTIVE}),
    }

    loan_number = models.CharField(max_length=20, unique=True)
    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.PROTECT, related_name="loans"
    )
    branch = models.ForeignKey(
        "branches.Branch", on_delete=models.PROTECT, related_name="loans", db_index=False
    )
    principal = money_field()
    annual_interest_rate = models.DecimalField(max_digits=5, decimal_places=2)
    tenure_months = models.PositiveSmallIntegerField()
    emi_amount = money_field()
    total_payable = money_field()
    amount_paid = money_field(default=ZERO)
    disbursed_on = models.DateField()
    first_due_date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(condition=Q(principal__gt=0), name="loan_principal_positive"),
            models.CheckConstraint(
                condition=Q(annual_interest_rate__gte=0, annual_interest_rate__lte=100),
                name="loan_interest_rate_range",
            ),
            models.CheckConstraint(
                condition=Q(tenure_months__gte=1, tenure_months__lte=360),
                name="loan_tenure_range",
            ),
            models.CheckConstraint(condition=Q(emi_amount__gt=0), name="loan_emi_positive"),
            models.CheckConstraint(
                condition=Q(total_payable__gte=F("principal")),
                name="loan_total_payable_covers_principal",
            ),
            models.CheckConstraint(
                condition=Q(amount_paid__gte=0, amount_paid__lte=F("total_payable")),
                name="loan_amount_paid_within_total",
            ),
            models.CheckConstraint(
                condition=Q(first_due_date__gt=F("disbursed_on")),
                name="loan_first_due_after_disbursal",
            ),
            models.CheckConstraint(
                condition=~Q(status="CLOSED")
                | Q(amount_paid=F("total_payable"), closed_at__isnull=False),
                name="loan_closed_only_when_fully_paid",
            ),
        ]
        indexes = [models.Index(fields=["branch", "status"], name="loan_branch_status_idx")]

    def __str__(self):
        return self.loan_number

    @property
    def outstanding(self) -> Decimal:
        return self.total_payable - self.amount_paid

    @property
    def is_closed(self) -> bool:
        return self.status == self.Status.CLOSED


class Installment(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PARTIALLY_PAID = "PARTIALLY_PAID", "Partially paid"
        PAID = "PAID", "Paid"

    loan = models.ForeignKey(
        Loan, on_delete=models.PROTECT, related_name="installments", db_index=False
    )
    installment_no = models.PositiveSmallIntegerField()
    due_date = models.DateField()
    principal_component = money_field()
    interest_component = money_field()
    amount_due = money_field()
    amount_paid = money_field(default=ZERO)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["loan_id", "installment_no"]
        constraints = [
            models.UniqueConstraint(
                fields=["loan", "installment_no"], name="uniq_installment_loan_number"
            ),
            models.CheckConstraint(
                condition=Q(amount_due__gt=0), name="installment_amount_due_positive"
            ),
            models.CheckConstraint(
                condition=Q(principal_component__gte=0, interest_component__gte=0),
                name="installment_components_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(amount_due=F("principal_component") + F("interest_component")),
                name="installment_amount_due_matches_components",
            ),
            models.CheckConstraint(
                condition=Q(amount_paid__gte=0, amount_paid__lte=F("amount_due")),
                name="installment_amount_paid_within_due",
            ),
            models.CheckConstraint(
                condition=Q(status="PENDING", amount_paid=0, paid_at__isnull=True)
                | Q(
                    status="PARTIALLY_PAID",
                    amount_paid__gt=0,
                    amount_paid__lt=F("amount_due"),
                    paid_at__isnull=True,
                )
                | Q(status="PAID", amount_paid=F("amount_due"), paid_at__isnull=False),
                name="installment_status_matches_amount_paid",
            ),
        ]
        indexes = [
            models.Index(fields=["due_date", "status"], name="installment_due_status_idx"),
            models.Index(
                fields=["due_date"],
                condition=~Q(status="PAID"),
                name="installment_unpaid_due_idx",
            ),
        ]

    def __str__(self):
        return f"{self.loan.loan_number} #{self.installment_no}"

    @property
    def outstanding(self) -> Decimal:
        return self.amount_due - self.amount_paid

    @property
    def is_overdue(self) -> bool:
        return self.status != self.Status.PAID and self.due_date < business_date()

    def sync_status(self, at: datetime | None = None) -> None:
        """Derive status and `paid_at` from `amount_paid` (kept consistent by a DB constraint)."""
        if self.amount_paid == self.amount_due:
            self.status = self.Status.PAID
            self.paid_at = self.paid_at or at or timezone.now()
        else:
            self.status = (
                self.Status.PARTIALLY_PAID if self.amount_paid > 0 else self.Status.PENDING
            )
            self.paid_at = None
