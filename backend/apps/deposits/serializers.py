from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.collections.models import Collection
from apps.core.money import ZERO, MoneyField
from apps.reconciliation.models import CashSubmission, Discrepancy

from . import selectors
from .models import BankAccount, BankDeposit

MAX_ITEMS_PER_BATCH = 500


def mask_account_number(last4: str) -> str:
    return f"XXXX{last4}"


# Bank accounts ----------------------------------------------------------------------------


class BankAccountSerializer(serializers.ModelSerializer):
    masked_account_number = serializers.SerializerMethodField()

    class Meta:
        model = BankAccount
        fields = (
            "id",
            "bank_name",
            "account_name",
            "masked_account_number",
            "ifsc",
            "is_gateway",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_masked_account_number(self, account: BankAccount) -> str:
        return mask_account_number(account.account_number_last4)


class BankAccountWriteSerializer(serializers.ModelSerializer):
    """Takes the full account number but only its last four digits are ever stored."""

    account_number = serializers.RegexField(
        r"^[0-9]{6,18}$",
        write_only=True,
        error_messages={"invalid": "Enter 6 to 18 digits."},
    )
    ifsc = serializers.RegexField(
        r"^[A-Za-z]{4}0[A-Za-z0-9]{6}$",
        required=False,
        allow_blank=True,
        error_messages={"invalid": "Enter a valid 11-character IFSC code."},
    )

    class Meta:
        model = BankAccount
        fields = ("bank_name", "account_name", "account_number", "ifsc", "is_gateway", "is_active")
        # The single-active-gateway rule is checked by the service and backed by the database.
        validators = []

    def validate_ifsc(self, value: str) -> str:
        return value.upper()

    def to_internal_value(self, data):
        values = super().to_internal_value(data)
        if "account_number" in values:
            values["account_number_last4"] = values.pop("account_number")[-4:]
        return values


class BankAccountBriefSerializer(serializers.ModelSerializer):
    masked_account_number = serializers.SerializerMethodField()

    class Meta:
        model = BankAccount
        fields = ("id", "bank_name", "account_name", "masked_account_number", "is_gateway")
        read_only_fields = fields

    def get_masked_account_number(self, account: BankAccount) -> str:
        return mask_account_number(account.account_number_last4)


# Deposits: input --------------------------------------------------------------------------


def _unique_ids(values: list[int]) -> list[int]:
    if len(set(values)) != len(values):
        raise serializers.ValidationError("Duplicate ids are not allowed.")
    return values


class DepositCreateSerializer(serializers.Serializer):
    submission_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
        max_length=MAX_ITEMS_PER_BATCH,
    )
    bank_account_id = serializers.IntegerField(min_value=1)
    deposited_amount = MoneyField()
    deposit_date = serializers.DateField()
    reference_number = serializers.CharField(max_length=64)
    remarks = serializers.CharField(required=False, allow_blank=True, default="", max_length=1000)

    def validate_submission_ids(self, value):
        return _unique_ids(value)


class DepositSettleSerializer(serializers.Serializer):
    settled_amount = MoneyField()
    settled_on = serializers.DateField()
    settlement_reference = serializers.CharField(max_length=64)
    remarks = serializers.CharField(required=False, allow_blank=True, default="", max_length=1000)
    reason_code = serializers.ChoiceField(
        choices=Discrepancy.ReasonCode.choices,
        default=Discrepancy.ReasonCode.BANK_ERROR,
        help_text="Classifies the settlement discrepancy when the credit differs.",
    )


class DepositFailSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=1000)


class GatewaySettlementCreateSerializer(serializers.Serializer):
    collection_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=False,
        max_length=MAX_ITEMS_PER_BATCH,
        help_text="UPI collections covered by this settlement; or use up_to_date.",
    )
    up_to_date = serializers.DateField(
        required=False,
        help_text="Settle every unsettled UPI collection captured on or before this date.",
    )
    gross_amount = MoneyField()
    fee_amount = MoneyField(min_value=ZERO, required=False, default=ZERO)
    tax_amount = MoneyField(min_value=ZERO, required=False, default=ZERO)
    net_amount = MoneyField(help_text="Amount credited to the bank: gross - fee - tax.")
    utr = serializers.CharField(max_length=64)
    settled_on = serializers.DateField()
    remarks = serializers.CharField(required=False, allow_blank=True, default="", max_length=1000)

    def validate_collection_ids(self, value):
        return _unique_ids(value)

    def validate(self, attrs):
        if ("collection_ids" in attrs) == ("up_to_date" in attrs):
            raise serializers.ValidationError("Provide either collection_ids or up_to_date.")
        return attrs


# Deposits: output -------------------------------------------------------------------------


class DepositSerializer(serializers.ModelSerializer):
    branch_code = serializers.CharField(source="branch.code", read_only=True, default=None)
    bank_account = BankAccountBriefSerializer(read_only=True)
    created_by_name = serializers.CharField(source="created_by.get_full_name", read_only=True)
    is_delayed = serializers.BooleanField(read_only=True)
    days_pending = serializers.IntegerField(read_only=True, allow_null=True)

    class Meta:
        model = BankDeposit
        fields = (
            "id",
            "deposit_number",
            "source",
            "status",
            "branch",
            "branch_code",
            "bank_account",
            "reference_number",
            "deposit_date",
            "expected_amount",
            "deposited_amount",
            "fee_amount",
            "tax_amount",
            "settled_amount",
            "settled_on",
            "is_delayed",
            "days_pending",
            "created_by",
            "created_by_name",
            "created_at",
        )
        read_only_fields = fields


class DepositSubmissionSerializer(serializers.ModelSerializer):
    agent_name = serializers.CharField(source="agent.get_full_name", read_only=True)
    # A GeneratedField is serialized as a float by default; money always goes out as a string.
    difference = MoneyField(min_value=None, read_only=True, allow_null=True)
    reviewed_by_name = serializers.CharField(
        source="reviewed_by.get_full_name", read_only=True, default=None
    )

    class Meta:
        model = CashSubmission
        fields = (
            "id",
            "submission_number",
            "status",
            "agent",
            "agent_name",
            "expected_amount",
            "received_amount",
            "difference",
            "submitted_at",
            "reviewed_at",
            "reviewed_by_name",
        )
        read_only_fields = fields


class DepositDiscrepancySerializer(serializers.ModelSerializer):
    class Meta:
        model = Discrepancy
        fields = ("id", "kind", "direction", "amount", "status", "reason_code", "created_at")
        read_only_fields = fields


class ReconciliationChainSerializer(serializers.Serializer):
    """Reconciled cash -> deposited -> settled. Differences are positive when money is short."""

    reconciled_amount = MoneyField(min_value=ZERO)
    deposited_amount = MoneyField(min_value=ZERO)
    fee_amount = MoneyField(min_value=ZERO)
    tax_amount = MoneyField(min_value=ZERO)
    expected_settlement_amount = MoneyField(min_value=None)
    settled_amount = MoneyField(min_value=ZERO, allow_null=True)
    deposit_difference = MoneyField(min_value=None)
    settlement_difference = MoneyField(min_value=None, allow_null=True)
    total_difference = MoneyField(min_value=None, allow_null=True)


class DepositDetailSerializer(DepositSerializer):
    settled_by_name = serializers.CharField(
        source="settled_by.get_full_name", read_only=True, default=None
    )
    failed_by_name = serializers.CharField(
        source="failed_by.get_full_name", read_only=True, default=None
    )
    collections_count = serializers.SerializerMethodField()
    submissions = serializers.SerializerMethodField()
    discrepancies = DepositDiscrepancySerializer(many=True, read_only=True)
    reconciliation = serializers.SerializerMethodField()

    class Meta(DepositSerializer.Meta):
        fields = (
            *DepositSerializer.Meta.fields,
            "settlement_reference",
            "remarks",
            "failure_reason",
            "settled_at",
            "settled_by",
            "settled_by_name",
            "failed_at",
            "failed_by",
            "failed_by_name",
            "collections_count",
            "submissions",
            "discrepancies",
            "reconciliation",
        )
        read_only_fields = fields

    @extend_schema_field(DepositSubmissionSerializer(many=True))
    def get_submissions(self, deposit: BankDeposit) -> list[dict]:
        """The hand-overs on the slip; a failed deposit lists the ones it returned to the branch."""
        if deposit.status != BankDeposit.Status.FAILED:
            submissions = deposit.submissions.all()
        else:
            # Failing a deposit detaches its hand-overs so the cash can be banked again.
            submissions = (
                CashSubmission.objects.select_related("agent", "reviewed_by")
                .filter(pk__in=selectors.deposited_submission_ids(deposit))
                .order_by("pk")
            )
        return DepositSubmissionSerializer(submissions, many=True).data

    @extend_schema_field(serializers.IntegerField())
    def get_collections_count(self, deposit: BankDeposit) -> int:
        if deposit.status != BankDeposit.Status.FAILED:
            return deposit.collections_count
        return Collection.objects.filter(
            submission_id__in=selectors.deposited_submission_ids(deposit)
        ).count()

    @extend_schema_field(ReconciliationChainSerializer)
    def get_reconciliation(self, deposit: BankDeposit) -> dict:
        expected_settlement = deposit.deposited_amount - deposit.fee_amount - deposit.tax_amount
        settled = deposit.settled_amount
        chain = {
            "reconciled_amount": deposit.expected_amount,
            "deposited_amount": deposit.deposited_amount,
            "fee_amount": deposit.fee_amount,
            "tax_amount": deposit.tax_amount,
            "expected_settlement_amount": expected_settlement,
            "settled_amount": settled,
            "deposit_difference": deposit.expected_amount - deposit.deposited_amount,
            "settlement_difference": None if settled is None else expected_settlement - settled,
            "total_difference": None if settled is None else deposit.net_expected_amount - settled,
        }
        return ReconciliationChainSerializer(chain).data


# Pending work queues ----------------------------------------------------------------------


class PendingCashQuerySerializer(serializers.Serializer):
    branch = serializers.IntegerField(
        min_value=1, required=False, help_text="Admins only; managers always see their branch."
    )


class UnsettledUpiQuerySerializer(serializers.Serializer):
    up_to_date = serializers.DateField(
        required=False, help_text="Only payments captured on or before this date."
    )


class PendingSubmissionSerializer(DepositSubmissionSerializer):
    branch_code = serializers.CharField(source="branch.code", read_only=True)

    class Meta(DepositSubmissionSerializer.Meta):
        fields = (*DepositSubmissionSerializer.Meta.fields, "branch", "branch_code")
        read_only_fields = fields


class PendingCashSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    total_amount = MoneyField(min_value=ZERO)
    has_more = serializers.BooleanField(
        help_text=f"True when only the oldest {MAX_ITEMS_PER_BATCH} (one batch) are listed."
    )
    submissions = PendingSubmissionSerializer(many=True)


class UnsettledCollectionSerializer(serializers.ModelSerializer):
    branch_code = serializers.CharField(source="branch.code", read_only=True)
    loan_number = serializers.CharField(source="loan.loan_number", read_only=True)
    customer_name = serializers.CharField(source="customer.full_name", read_only=True)

    class Meta:
        model = Collection
        fields = (
            "id",
            "receipt_number",
            "amount",
            "collected_at",
            "gateway_payment_id",
            "branch",
            "branch_code",
            "loan_number",
            "customer_name",
        )
        read_only_fields = fields


class UnsettledUpiSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    total_amount = MoneyField(min_value=ZERO)
    has_more = serializers.BooleanField(
        help_text=f"True when only the oldest {MAX_ITEMS_PER_BATCH} (one batch) are listed."
    )
    collections = UnsettledCollectionSerializer(many=True)
