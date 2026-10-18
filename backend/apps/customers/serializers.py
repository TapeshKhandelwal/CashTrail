from rest_framework import serializers

from apps.accounts.models import User
from apps.accounts.serializers import PhoneField
from apps.branches.models import Branch
from apps.core.money import MoneyField
from apps.loans.models import Loan

from .models import Customer


def mask_phone(phone: str) -> str:
    return f"{'*' * (len(phone) - 4)}{phone[-4:]}" if len(phone) > 4 else phone


def hides_contact_details(request) -> bool:
    """Finance reconciles money, not people: it sees customers' phone numbers masked."""
    return request is not None and getattr(request.user, "is_finance", False)


class LoanSummarySerializer(serializers.ModelSerializer):
    outstanding = MoneyField(read_only=True)
    overdue_amount = MoneyField(read_only=True)
    next_due_date = serializers.DateField(read_only=True, allow_null=True)

    class Meta:
        model = Loan
        fields = (
            "id",
            "loan_number",
            "status",
            "principal",
            "annual_interest_rate",
            "tenure_months",
            "emi_amount",
            "total_payable",
            "amount_paid",
            "outstanding",
            "overdue_amount",
            "next_due_date",
            "disbursed_on",
        )
        read_only_fields = fields


class CustomerSerializer(serializers.ModelSerializer):
    """Customer with its repayment position (see `selectors.with_dues`)."""

    branch_code = serializers.CharField(source="branch.code", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    assigned_agent_name = serializers.SerializerMethodField()
    outstanding = MoneyField(read_only=True)
    overdue_amount = MoneyField(read_only=True)
    due_today = MoneyField(read_only=True)
    next_due_date = serializers.DateField(read_only=True, allow_null=True)
    active_loans = serializers.IntegerField(read_only=True)

    class Meta:
        model = Customer
        fields = (
            "id",
            "customer_code",
            "full_name",
            "phone",
            "email",
            "address",
            "branch",
            "branch_code",
            "branch_name",
            "assigned_agent",
            "assigned_agent_name",
            "is_active",
            "outstanding",
            "overdue_amount",
            "due_today",
            "next_due_date",
            "active_loans",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_assigned_agent_name(self, customer: Customer) -> str | None:
        agent = customer.assigned_agent
        return (agent.get_full_name() or agent.username) if agent else None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if hides_contact_details(self.context.get("request")):
            data["phone"] = mask_phone(data["phone"])
        return data


class CustomerDetailSerializer(CustomerSerializer):
    loans = LoanSummarySerializer(many=True, read_only=True)

    class Meta(CustomerSerializer.Meta):
        fields = (*CustomerSerializer.Meta.fields, "loans")
        read_only_fields = fields


def _manager_branch_id(context) -> int | None:
    """Managers pick only from their own branch, so other branches' ids read as unknown."""
    request = context.get("request")
    return request.user.branch_id if request and request.user.is_branch_manager else None


AGENTS = User.objects.filter(role=User.Role.AGENT)


class CustomerCreateSerializer(serializers.ModelSerializer):
    phone = PhoneField()
    branch = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.all(),
        required=False,
        allow_null=True,
        help_text="Required for admins; branch managers always create in their own branch.",
    )
    assigned_agent = serializers.PrimaryKeyRelatedField(
        queryset=AGENTS, required=False, allow_null=True
    )

    class Meta:
        model = Customer
        fields = ("full_name", "phone", "email", "address", "branch", "assigned_agent")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if (branch_id := _manager_branch_id(self.context)) is not None:
            self.fields["branch"].queryset = Branch.objects.filter(pk=branch_id)
            self.fields["assigned_agent"].queryset = AGENTS.filter(branch=branch_id)


class CustomerUpdateSerializer(serializers.ModelSerializer):
    phone = PhoneField(required=False)

    class Meta:
        model = Customer
        fields = ("full_name", "phone", "email", "address", "is_active")


class CustomerAssignSerializer(serializers.Serializer):
    agent_id = serializers.PrimaryKeyRelatedField(
        source="agent",
        queryset=AGENTS,
        allow_null=True,
        help_text="Active agent of the customer's branch; null removes the assignment.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if (branch_id := _manager_branch_id(self.context)) is not None:
            self.fields["agent_id"].queryset = AGENTS.filter(branch=branch_id)
