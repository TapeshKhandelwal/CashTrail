from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.collections.models import Allocation, Collection
from apps.core.money import ZERO, MoneyField
from apps.customers.serializers import hides_contact_details, mask_phone

from .models import Installment, Loan
from .schedule import MAX_TENURE_MONTHS
from .services import MAX_ANNUAL_RATE


class InterestRateField(serializers.DecimalField):
    """Annual percentage with two places, e.g. `"12.50"`; floats are rejected like money."""

    default_error_messages = {
        "float": 'Send the rate as a string (e.g. "12.50"), not a floating-point number.',
    }

    def __init__(self, **kwargs):
        kwargs.setdefault("min_value", ZERO)
        kwargs.setdefault("max_value", MAX_ANNUAL_RATE)
        super().__init__(max_digits=5, decimal_places=2, **kwargs)

    def to_internal_value(self, data):
        if isinstance(data, float):
            self.fail("float")
        return super().to_internal_value(data)


class LoanTermsSerializer(serializers.Serializer):
    principal = MoneyField()
    annual_interest_rate = InterestRateField()
    tenure_months = serializers.IntegerField(min_value=1, max_value=MAX_TENURE_MONTHS)
    disbursed_on = serializers.DateField(required=False, help_text="Defaults to today.")
    first_due_date = serializers.DateField(
        required=False, help_text="Defaults to one month after disbursal."
    )


class LoanCreateSerializer(LoanTermsSerializer):
    customer_id = serializers.IntegerField(min_value=1)


class NextDueSerializer(serializers.Serializer):
    installment_no = serializers.IntegerField(source="next_due_installment_no")
    due_date = serializers.DateField(source="next_due_date")
    amount = MoneyField(source="next_due_amount", min_value=ZERO)


class LoanSerializer(serializers.ModelSerializer):
    """Expects a loan from `selectors.loans_with_balances`."""

    customer_code = serializers.CharField(source="customer.customer_code")
    customer_name = serializers.CharField(source="customer.full_name")
    customer_phone = serializers.CharField(source="customer.phone")
    branch_code = serializers.CharField(source="branch.code")
    branch_name = serializers.CharField(source="branch.name")
    agent = serializers.IntegerField(source="customer.assigned_agent_id", allow_null=True)
    agent_name = serializers.CharField(
        source="customer.assigned_agent.get_full_name", default=None, allow_null=True
    )
    outstanding = MoneyField(min_value=ZERO)
    overdue_amount = MoneyField(min_value=ZERO)
    paid_installments = serializers.IntegerField()
    next_due = serializers.SerializerMethodField()
    terms_locked = serializers.BooleanField(
        help_text="True once any repayment exists; the loan terms can no longer be edited."
    )

    class Meta:
        model = Loan
        fields = (
            "id",
            "loan_number",
            "customer",
            "customer_code",
            "customer_name",
            "customer_phone",
            "branch",
            "branch_code",
            "branch_name",
            "agent",
            "agent_name",
            "principal",
            "annual_interest_rate",
            "tenure_months",
            "emi_amount",
            "total_payable",
            "amount_paid",
            "outstanding",
            "overdue_amount",
            "paid_installments",
            "next_due",
            "disbursed_on",
            "first_due_date",
            "status",
            "closed_at",
            "terms_locked",
            "created_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    @extend_schema_field(NextDueSerializer(allow_null=True))
    def get_next_due(self, loan: Loan):
        if loan.next_due_date is None:
            return None
        return NextDueSerializer(loan).data

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if hides_contact_details(self.context.get("request")):
            data["customer_phone"] = mask_phone(data["customer_phone"])
        return data


class InstallmentSerializer(serializers.ModelSerializer):
    outstanding = MoneyField(min_value=ZERO, read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = Installment
        fields = (
            "id",
            "installment_no",
            "due_date",
            "principal_component",
            "interest_component",
            "amount_due",
            "amount_paid",
            "outstanding",
            "status",
            "is_overdue",
            "paid_at",
        )
        read_only_fields = fields


class ScheduleRowSerializer(serializers.Serializer):
    installment_no = serializers.IntegerField()
    due_date = serializers.DateField()
    opening_balance = MoneyField(min_value=ZERO)
    principal_component = MoneyField(min_value=ZERO)
    interest_component = MoneyField(min_value=ZERO)
    amount_due = MoneyField()
    closing_balance = MoneyField(min_value=ZERO)


class SchedulePreviewSerializer(serializers.Serializer):
    principal = MoneyField()
    annual_interest_rate = InterestRateField()
    tenure_months = serializers.IntegerField()
    disbursed_on = serializers.DateField()
    first_due_date = serializers.DateField()
    emi_amount = MoneyField()
    total_payable = MoneyField()
    total_interest = MoneyField(min_value=ZERO)
    installments = ScheduleRowSerializer(many=True, source="rows")


class RepaymentAllocationSerializer(serializers.ModelSerializer):
    installment_no = serializers.IntegerField(source="installment.installment_no")
    due_date = serializers.DateField(source="installment.due_date")

    class Meta:
        model = Allocation
        fields = ("installment", "installment_no", "due_date", "amount", "reversed_at")
        read_only_fields = fields


class RepaymentSerializer(serializers.ModelSerializer):
    """A collection as it appears in a loan's repayment history."""

    agent_name = serializers.CharField(source="agent.get_full_name", default=None, allow_null=True)
    submission_number = serializers.CharField(
        source="submission.submission_number", default=None, allow_null=True
    )
    deposit_number = serializers.CharField(
        source="deposit.deposit_number", default=None, allow_null=True
    )
    allocations = RepaymentAllocationSerializer(many=True)

    class Meta:
        model = Collection
        fields = (
            "id",
            "receipt_number",
            "amount",
            "mode",
            "status",
            "agent",
            "agent_name",
            "gateway_payment_id",
            "remarks",
            "collected_at",
            "submitted_at",
            "branch_received_at",
            "deposited_at",
            "settled_at",
            "voided_at",
            "void_reason",
            "submission_number",
            "deposit_number",
            "allocations",
        )
        read_only_fields = fields
