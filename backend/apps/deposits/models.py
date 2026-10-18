from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.models.functions import Trim, Upper

from apps.core.dates import business_date
from apps.core.models import StateMachineMixin, TimeStampedModel, money_field
from apps.core.money import ZERO


def normalize_reference(value: str) -> str:
    """Bank references compare case- and whitespace-insensitively: ` utr 12ab ` == `UTR12AB`."""
    return "".join(value.split()).upper()


class BankAccount(TimeStampedModel):
    """A company account that branch cash (or gateway settlements) lands in."""

    bank_name = models.CharField(max_length=100)
    account_name = models.CharField(max_length=150)
    account_number_last4 = models.CharField(
        max_length=4, help_text="Only the last four digits are stored."
    )
    ifsc = models.CharField(max_length=11, blank=True)
    is_gateway = models.BooleanField(
        default=False, help_text="Virtual account for payment gateway settlements."
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["bank_name", "account_name"]
        constraints = [
            models.CheckConstraint(
                condition=Q(account_number_last4__regex=r"^[0-9]{4}$"),
                name="bank_account_last4_digits",
            ),
            models.CheckConstraint(
                condition=Q(ifsc="") | Q(ifsc__regex=r"^[A-Z]{4}0[A-Z0-9]{6}$"),
                name="bank_account_ifsc_format",
            ),
            models.UniqueConstraint(
                fields=["is_gateway"],
                condition=Q(is_gateway=True, is_active=True),
                name="uniq_active_gateway_bank_account",
            ),
        ]

    def __str__(self):
        return f"{self.bank_name} ••{self.account_number_last4}"


def delayed_q(today: date | None = None) -> Q:
    """Pending beyond the settlement SLA, as a filter usable in aggregates too.

    Mirrors `BankDeposit.is_delayed`.
    """
    cutoff = (today or business_date()) - timedelta(days=settings.SETTLEMENT_SLA_DAYS)
    return Q(status=BankDeposit.Status.PENDING, deposit_date__lt=cutoff)


class BankDepositQuerySet(models.QuerySet):
    def pending(self):
        return self.filter(status=BankDeposit.Status.PENDING)

    def delayed(self, today: date | None = None):
        return self.filter(delayed_q(today))


class BankDeposit(StateMachineMixin, TimeStampedModel):
    """Cash paid into a bank account, or a gateway settlement batch for UPI collections."""

    class Source(models.TextChoices):
        CASH = "CASH", "Branch cash"
        GATEWAY = "GATEWAY", "Payment gateway"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending settlement"
        SETTLED = "SETTLED", "Settled"
        SETTLED_WITH_MISMATCH = "SETTLED_WITH_MISMATCH", "Settled with mismatch"
        FAILED = "FAILED", "Failed"

    SETTLED_STATUSES = frozenset({Status.SETTLED, Status.SETTLED_WITH_MISMATCH})
    TRANSITIONS = {
        Status.PENDING: frozenset({Status.SETTLED, Status.SETTLED_WITH_MISMATCH, Status.FAILED}),
    }

    deposit_number = models.CharField(max_length=32, unique=True)
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.CASH)
    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="bank_deposits",
        db_index=False,
        help_text="Empty for gateway settlements.",
    )
    bank_account = models.ForeignKey(BankAccount, on_delete=models.PROTECT, related_name="deposits")
    reference_number = models.CharField(
        max_length=64, help_text="Slip number, bank transaction ref or UTR."
    )
    deposit_date = models.DateField()
    expected_amount = money_field(
        help_text="Server-computed: approved cash received (cash) or UPI collections (gateway)."
    )
    deposited_amount = money_field(help_text="As on the deposit slip / gateway settlement report.")
    fee_amount = money_field(default=ZERO)
    tax_amount = money_field(default=ZERO)
    settled_amount = money_field(
        null=True, blank=True, help_text="As credited on the bank statement."
    )
    settled_on = models.DateField(null=True, blank=True)
    settlement_reference = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.PENDING)
    remarks = models.TextField(blank=True)
    failure_reason = models.TextField(blank=True)
    settled_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_deposits"
    )
    settled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    failed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    idempotency_key = models.UUIDField(null=True, blank=True)

    objects = BankDepositQuerySet.as_manager()

    class Meta:
        ordering = ["-deposit_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["bank_account", "reference_number"],
                name="uniq_bank_deposit_account_reference",
            ),
            models.UniqueConstraint(
                fields=["created_by", "idempotency_key"],
                name="uniq_bank_deposit_creator_idempotency_key",
            ),
            models.CheckConstraint(
                condition=~Q(reference_number="")
                & Q(reference_number=Upper(Trim("reference_number"))),
                name="bank_deposit_reference_normalized",
            ),
            models.CheckConstraint(
                condition=Q(expected_amount__gte=0), name="bank_deposit_expected_non_negative"
            ),
            models.CheckConstraint(
                condition=Q(deposited_amount__gt=0), name="bank_deposit_amount_positive"
            ),
            models.CheckConstraint(
                condition=Q(fee_amount__gte=0, tax_amount__gte=0),
                name="bank_deposit_charges_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(source="GATEWAY") | Q(fee_amount=0, tax_amount=0),
                name="bank_deposit_charges_only_for_gateway",
            ),
            models.CheckConstraint(
                condition=Q(source="CASH", branch__isnull=False)
                | Q(source="GATEWAY", branch__isnull=True),
                name="bank_deposit_branch_matches_source",
            ),
            models.CheckConstraint(
                condition=Q(settled_amount__isnull=True) | Q(settled_amount__gte=0),
                name="bank_deposit_settled_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(status="PENDING", settled_amount__isnull=True, settled_at__isnull=True)
                | Q(
                    status__in=["SETTLED", "SETTLED_WITH_MISMATCH"],
                    settled_amount__isnull=False,
                    settled_on__isnull=False,
                    settled_at__isnull=False,
                )
                | (Q(status="FAILED", failed_at__isnull=False) & ~Q(failure_reason="")),
                name="bank_deposit_settlement_consistency",
            ),
        ]
        indexes = [
            models.Index(
                fields=["branch", "status", "deposit_date"], name="deposit_branch_status_idx"
            ),
            models.Index(
                fields=["deposit_date"], condition=Q(status="PENDING"), name="deposit_pending_idx"
            ),
            models.Index(fields=["source", "status"], name="deposit_source_status_idx"),
            models.Index(fields=["settled_on"], name="deposit_settled_on_idx"),
        ]

    def __str__(self):
        return self.deposit_number

    def save(self, *args, **kwargs):
        self.reference_number = normalize_reference(self.reference_number)
        super().save(*args, **kwargs)

    @property
    def is_locked(self) -> bool:
        return self.status != self.Status.PENDING

    @property
    def is_settled(self) -> bool:
        return self.status in self.SETTLED_STATUSES

    @property
    def net_expected_amount(self) -> Decimal:
        """What should reach the bank: gateway settlements arrive net of fee and tax."""
        return self.expected_amount - self.fee_amount - self.tax_amount

    @property
    def days_pending(self) -> int | None:
        if self.status != self.Status.PENDING:
            return None
        return (business_date() - self.deposit_date).days

    @property
    def is_delayed(self) -> bool:
        return (
            self.status == self.Status.PENDING
            and self.deposit_date + timedelta(days=settings.SETTLEMENT_SLA_DAYS) < business_date()
        )
