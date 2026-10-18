from rest_framework import serializers

from apps.accounts.models import User
from apps.branches.models import Branch
from apps.collections.models import Collection
from apps.core.dates import business_date
from apps.deposits.models import BankDeposit
from apps.reconciliation.models import CashSubmission, Discrepancy

from .selectors import DashboardFilters, visible_agents, visible_branches


def _amount(**kwargs) -> serializers.DecimalField:
    # Totals can outgrow a single NUMERIC(14,2) column, so allow two extra digits.
    return serializers.DecimalField(max_digits=16, decimal_places=2, read_only=True, **kwargs)


def _percent(help_text: str) -> serializers.DecimalField:
    return serializers.DecimalField(
        max_digits=9, decimal_places=2, allow_null=True, read_only=True, help_text=help_text
    )


# Query parameters ------------------------------------------------------------------

# Voided receipts are outside every dashboard total, so they are not a status to narrow to.
DASHBOARD_STATUSES = [
    choice for choice in Collection.Status.choices if choice[0] != Collection.Status.VOIDED
]


class DashboardFilterSerializer(serializers.Serializer):
    """Shared query parameters. Branch and agent must be within the caller's scope."""

    max_days: int | None = None

    date_from = serializers.DateField(
        required=False, help_text="Defaults to the first day of `date_to`'s month."
    )
    date_to = serializers.DateField(required=False, help_text="Defaults to today (IST).")
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all(), required=False)
    agent = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role=User.Role.AGENT), required=False
    )
    status = serializers.ChoiceField(
        choices=DASHBOARD_STATUSES,
        required=False,
        help_text=(
            "Receipt status; narrows every receipt figure (collected, settled, cash position, "
            "trend, lifecycle). Voided receipts are counted on their own."
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request is not None:
            self.fields["branch"].queryset = visible_branches(request.user)
            self.fields["agent"].queryset = visible_agents(request.user)

    def validate(self, attrs):
        date_to = attrs.get("date_to") or business_date()
        date_from = attrs.get("date_from") or date_to.replace(day=1)
        if date_from > date_to:
            raise serializers.ValidationError({"date_from": "Must be on or before date_to."})
        if self.max_days and (date_to - date_from).days >= self.max_days:
            raise serializers.ValidationError(
                {"date_to": f"The range can span at most {self.max_days} days."}
            )
        return {**attrs, "date_from": date_from, "date_to": date_to}

    def to_filters(self) -> DashboardFilters:
        return DashboardFilters(**self.validated_data)


class TrendFilterSerializer(DashboardFilterSerializer):
    max_days = 366


class CollectionReportFilterSerializer(DashboardFilterSerializer):
    status = serializers.ChoiceField(choices=Collection.Status.choices, required=False)


class SubmissionReportFilterSerializer(DashboardFilterSerializer):
    status = serializers.ChoiceField(choices=CashSubmission.Status.choices, required=False)


class DepositReportFilterSerializer(DashboardFilterSerializer):
    status = serializers.ChoiceField(choices=BankDeposit.Status.choices, required=False)


class DiscrepancyReportFilterSerializer(DashboardFilterSerializer):
    status = serializers.ChoiceField(choices=Discrepancy.Status.choices, required=False)


# Responses -------------------------------------------------------------------------


class TallySerializer(serializers.Serializer):
    amount = _amount()
    count = serializers.IntegerField(read_only=True)


class CollectedSerializer(TallySerializer):
    cash = TallySerializer()
    upi = TallySerializer()


class CashAgeingBucketSerializer(TallySerializer):
    bucket = serializers.CharField(read_only=True)
    label = serializers.CharField(read_only=True)


class DepositStatusTallySerializer(TallySerializer):
    status = serializers.ChoiceField(choices=BankDeposit.Status.choices, read_only=True)


class DepositsSerializer(TallySerializer):
    by_status = DepositStatusTallySerializer(many=True)


class DiscrepancyKindTallySerializer(TallySerializer):
    kind = serializers.ChoiceField(choices=Discrepancy.Kind.choices, read_only=True)


class DiscrepancyTotalsSerializer(serializers.Serializer):
    open = TallySerializer(help_text="Currently open, regardless of when raised.")
    open_by_kind = DiscrepancyKindTallySerializer(many=True)
    raised = TallySerializer(help_text="Raised within the period.")
    resolved = TallySerializer(help_text="Resolved or written off within the period.")


class DashboardSummarySerializer(serializers.Serializer):
    date_from = serializers.DateField(read_only=True)
    date_to = serializers.DateField(read_only=True)
    expected = TallySerializer(help_text="Installments falling due in the period.")
    collected = CollectedSerializer(help_text="Receipts in the period, excluding voided ones.")
    voided = TallySerializer()
    cash_with_agents = TallySerializer(help_text="Cash receipts not yet handed over (now).")
    pending_verification = TallySerializer(help_text="Cash handed over, awaiting review (now).")
    cash_ageing = CashAgeingBucketSerializer(
        many=True, help_text="Cash receipts not yet handed over, by age (now)."
    )
    branch_received = TallySerializer(help_text="Cash counted at branches in the period.")
    at_branch = TallySerializer(help_text="Approved branch cash not yet deposited (now).")
    pending_deposits = TallySerializer(
        help_text="Branch cash deposits awaiting bank confirmation, whenever deposited (now)."
    )
    deposits = DepositsSerializer(
        help_text=(
            "Branch cash deposited in the period, excluding failed deposits "
            "(listed only under `by_status`)."
        )
    )
    settled = TallySerializer(
        help_text="Receipts credited to the company account in the period, by bank date."
    )
    delayed_settlements = TallySerializer(help_text="Pending past the settlement SLA (now).")
    outstanding = TallySerializer(help_text="Balance of active loans (now).")
    overdue = TallySerializer(help_text="Unpaid amounts of past-due installments (now).")
    discrepancies = DiscrepancyTotalsSerializer()
    collection_efficiency = _percent("Collected as a percentage of expected.")
    deposit_accuracy = _percent("Share of settled cash deposits that matched the bank exactly.")
    avg_settlement_lag_days = serializers.DecimalField(
        max_digits=7, decimal_places=1, allow_null=True, read_only=True
    )


class TrendPointSerializer(serializers.Serializer):
    date = serializers.DateField(read_only=True)
    expected = _amount()
    collected = _amount()
    settled = _amount(help_text="Receipts credited to the company account that day.")


class LifecycleStageSerializer(TallySerializer):
    stage = serializers.CharField(read_only=True)
    label = serializers.CharField(read_only=True)


class LifecycleStatusSerializer(TallySerializer):
    status = serializers.ChoiceField(choices=Collection.Status.choices, read_only=True)
    label = serializers.CharField(read_only=True)


class LifecycleSerializer(serializers.Serializer):
    date_from = serializers.DateField(read_only=True)
    date_to = serializers.DateField(read_only=True)
    expected = TallySerializer()
    stages = LifecycleStageSerializer(
        many=True, help_text="Receipts that reached at least this stage."
    )
    by_status = LifecycleStatusSerializer(many=True, help_text="Receipts by current status.")


class BranchRefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = ("id", "code", "name")
        read_only_fields = fields


class AgentRefSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="get_full_name", read_only=True)
    branch_code = serializers.CharField(source="branch.code", read_only=True)

    class Meta:
        model = User
        fields = ("id", "username", "full_name", "branch", "branch_code", "is_active")
        read_only_fields = fields


class TeamRowSerializer(serializers.Serializer):
    expected = TallySerializer()
    collected = TallySerializer()
    cash_with_agents = TallySerializer()
    pending_verification = TallySerializer()
    branch_received = TallySerializer()
    outstanding = TallySerializer()
    overdue = TallySerializer()
    open_discrepancies = TallySerializer()
    collection_efficiency = _percent("Collected as a percentage of expected.")


class BranchRowSerializer(TeamRowSerializer):
    branch = BranchRefSerializer()
    at_branch = TallySerializer()
    deposited = TallySerializer()
    settled = TallySerializer()
    delayed_settlements = TallySerializer()


class AgentRowSerializer(TeamRowSerializer):
    agent = AgentRefSerializer()
    oldest_cash_held_at = serializers.DateTimeField(allow_null=True, read_only=True)
    rejected_submissions = TallySerializer()
