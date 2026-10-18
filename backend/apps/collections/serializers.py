from rest_framework import serializers

from apps.core.money import ZERO, MoneyField

from . import selectors
from .models import Allocation, Collection


class CollectionSerializer(serializers.ModelSerializer):
    loan_number = serializers.CharField(source="loan.loan_number")
    customer_code = serializers.CharField(source="customer.customer_code")
    customer_name = serializers.CharField(source="customer.full_name")
    branch_code = serializers.CharField(source="branch.code")
    agent_name = serializers.CharField(source="agent.get_full_name", allow_null=True)
    amount = MoneyField()
    balance_after = MoneyField(
        min_value=ZERO,
        allow_null=True,
        help_text="Loan balance right after this receipt was applied, as recorded.",
    )

    class Meta:
        model = Collection
        fields = (
            "id",
            "receipt_number",
            "loan",
            "loan_number",
            "customer",
            "customer_code",
            "customer_name",
            "branch",
            "branch_code",
            "agent",
            "agent_name",
            "amount",
            "balance_after",
            "mode",
            "status",
            "collected_at",
            "submitted_at",
            "branch_received_at",
            "deposited_at",
            "settled_at",
            "voided_at",
            "gateway_payment_id",
            "remarks",
        )
        read_only_fields = fields


class AllocationSerializer(serializers.ModelSerializer):
    installment_no = serializers.IntegerField(source="installment.installment_no")
    due_date = serializers.DateField(source="installment.due_date")
    amount = MoneyField()

    class Meta:
        model = Allocation
        fields = ("id", "installment", "installment_no", "due_date", "amount", "reversed_at")
        read_only_fields = fields


class TimelineStepSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Collection.Status.choices)
    label = serializers.CharField()
    reached = serializers.BooleanField()
    at = serializers.DateTimeField(allow_null=True)
    reference = serializers.CharField(allow_null=True)


class CollectionDetailSerializer(CollectionSerializer):
    """The receipt: allocations, where the money is now, and the balance it left on the loan."""

    loan_outstanding = MoneyField(
        source="loan.outstanding", min_value=ZERO, help_text="The loan's balance today."
    )
    submission_number = serializers.CharField(
        source="submission.submission_number", allow_null=True
    )
    deposit_number = serializers.CharField(source="deposit.deposit_number", allow_null=True)
    voided_by_name = serializers.CharField(source="voided_by.get_full_name", allow_null=True)
    allocations = AllocationSerializer(many=True)
    timeline = serializers.SerializerMethodField()

    class Meta(CollectionSerializer.Meta):
        fields = (
            *CollectionSerializer.Meta.fields,
            "loan_outstanding",
            "submission",
            "submission_number",
            "deposit",
            "deposit_number",
            "void_reason",
            "voided_by",
            "voided_by_name",
            "allocations",
            "timeline",
        )
        read_only_fields = fields

    @staticmethod
    def get_timeline(obj) -> list[dict]:
        return TimelineStepSerializer(selectors.lifecycle_timeline(obj), many=True).data


class CollectionCreateSerializer(serializers.Serializer):
    loan_id = serializers.IntegerField(min_value=1)
    amount = MoneyField()
    mode = serializers.ChoiceField(choices=Collection.Mode.choices, default=Collection.Mode.CASH)
    remarks = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    confirm_duplicate = serializers.BooleanField(
        default=False,
        help_text="Record even though a matching receipt was issued moments ago.",
    )

    def validate_mode(self, value):
        if value != Collection.Mode.CASH:
            raise serializers.ValidationError(
                "UPI repayments are recorded through the payment gateway."
            )
        return value


class VoidCollectionSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500)


class DailySummaryQuerySerializer(serializers.Serializer):
    date = serializers.DateField(required=False, help_text="Business date; defaults to today.")
    branch = serializers.IntegerField(required=False, min_value=1)
    agent = serializers.IntegerField(required=False, min_value=1)


class DailySummarySerializer(serializers.Serializer):
    date = serializers.DateField()
    count = serializers.IntegerField()
    total_amount = MoneyField(min_value=ZERO)
    cash_count = serializers.IntegerField()
    cash_amount = MoneyField(min_value=ZERO)
    upi_count = serializers.IntegerField()
    upi_amount = MoneyField(min_value=ZERO)
    voided_count = serializers.IntegerField()
    unsubmitted_count = serializers.IntegerField(help_text="Cash receipts not yet handed over.")
    unsubmitted_cash = MoneyField(min_value=ZERO, help_text="Cash still held by the agent(s).")
