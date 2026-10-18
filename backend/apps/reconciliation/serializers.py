from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.collections.models import Collection
from apps.core.dates import business_date
from apps.core.money import ZERO, MoneyField

from . import selectors
from .denominations import normalize_denominations
from .models import CashSubmission, Discrepancy


def _amount(**kwargs) -> serializers.DecimalField:
    """Read-only money output; unlike `MoneyField` it may be zero or negative."""
    return serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True, **kwargs)


class DenominationsField(serializers.DictField):
    """`{"500": 90, "200": 10}`: rupee denomination -> count of notes/coins."""

    child = serializers.IntegerField(min_value=0)

    def to_internal_value(self, data):
        counts = super().to_internal_value(data)
        try:
            return normalize_denominations(counts)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from None


# Cash submissions


class SubmissionCollectionSerializer(serializers.ModelSerializer):
    loan_number = serializers.CharField(source="loan.loan_number", read_only=True)
    customer_name = serializers.CharField(source="customer.full_name", read_only=True)

    class Meta:
        model = Collection
        fields = (
            "id",
            "receipt_number",
            "loan",
            "loan_number",
            "customer",
            "customer_name",
            "amount",
            "status",
            "collected_at",
        )
        read_only_fields = fields


class SubmissionDiscrepancySerializer(serializers.ModelSerializer):
    class Meta:
        model = Discrepancy
        fields = (
            "id",
            "kind",
            "direction",
            "amount",
            "status",
            "reason_code",
            "notes",
            "resolution_notes",
            "resolved_at",
            "created_at",
        )
        read_only_fields = fields


class CashSubmissionSerializer(serializers.ModelSerializer):
    agent_name = serializers.CharField(source="agent.get_full_name", read_only=True)
    agent_username = serializers.CharField(source="agent.username", read_only=True)
    branch_code = serializers.CharField(source="branch.code", read_only=True)
    received_amount = _amount(allow_null=True)
    difference = _amount(
        allow_null=True,
        help_text="Expected minus received: positive is a shortage, negative an excess.",
    )
    reviewed_by_name = serializers.CharField(
        source="reviewed_by.get_full_name", read_only=True, default=None
    )
    deposit_number = serializers.CharField(
        source="deposit.deposit_number", read_only=True, default=None
    )
    collection_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = CashSubmission
        fields = (
            "id",
            "submission_number",
            "agent",
            "agent_name",
            "agent_username",
            "branch",
            "branch_code",
            "expected_amount",
            "declared_amount",
            "received_amount",
            "difference",
            "status",
            "collection_count",
            "submitted_at",
            "reviewed_at",
            "reviewed_by",
            "reviewed_by_name",
            "review_remarks",
            "rejection_reason",
            "deposit",
            "deposit_number",
        )
        read_only_fields = fields


class CashSubmissionDetailSerializer(CashSubmissionSerializer):
    denominations = serializers.DictField(
        child=serializers.IntegerField(),
        read_only=True,
        allow_null=True,
        help_text="The agent's own count; null when handed over as receipted.",
    )
    received_denominations = serializers.DictField(
        child=serializers.IntegerField(),
        read_only=True,
        allow_null=True,
        help_text="The branch manager's count, when itemised.",
    )
    collections = serializers.SerializerMethodField()
    discrepancies = SubmissionDiscrepancySerializer(many=True, read_only=True)

    class Meta(CashSubmissionSerializer.Meta):
        fields = (
            *CashSubmissionSerializer.Meta.fields,
            "denominations",
            "received_denominations",
            "collections",
            "discrepancies",
        )
        read_only_fields = fields

    @extend_schema_field(SubmissionCollectionSerializer(many=True))
    def get_collections(self, submission):
        return SubmissionCollectionSerializer(
            selectors.submission_collections(submission), many=True
        ).data


class CashSubmissionCreateSerializer(serializers.Serializer):
    collection_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), min_length=1, max_length=500
    )
    declared_amount = MoneyField(
        min_value=ZERO, help_text="Cash the agent says they are handing over."
    )
    denominations = DenominationsField(required=False, allow_null=True)

    def validate_collection_ids(self, value):
        if len(set(value)) != len(value):
            raise serializers.ValidationError("Each receipt can be included only once.")
        return value


class SubmissionApproveSerializer(serializers.Serializer):
    received_amount = MoneyField(min_value=ZERO, help_text="Cash counted at the branch.")
    denominations = DenominationsField(
        required=False, allow_null=True, help_text="When given, must add up to received_amount."
    )
    reason_code = serializers.ChoiceField(
        choices=Discrepancy.ReasonCode.choices,
        required=False,
        help_text="Required when the received amount differs from the expected amount.",
    )
    remarks = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=2000,
        help_text="Required when the received amount differs from the expected amount.",
    )


class SubmissionRejectSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=2000)


# Discrepancies


class DiscrepancySerializer(serializers.ModelSerializer):
    branch_code = serializers.CharField(source="branch.code", read_only=True, default=None)
    agent_name = serializers.CharField(source="agent.get_full_name", read_only=True, default=None)
    submission_number = serializers.CharField(
        source="submission.submission_number", read_only=True, default=None
    )
    deposit_number = serializers.CharField(
        source="deposit.deposit_number", read_only=True, default=None
    )
    raised_by_name = serializers.CharField(
        source="raised_by.get_full_name", read_only=True, default=None
    )
    resolved_by_name = serializers.CharField(
        source="resolved_by.get_full_name", read_only=True, default=None
    )

    class Meta:
        model = Discrepancy
        fields = (
            "id",
            "kind",
            "direction",
            "amount",
            "status",
            "reason_code",
            "notes",
            "submission",
            "submission_number",
            "deposit",
            "deposit_number",
            "branch",
            "branch_code",
            "agent",
            "agent_name",
            "raised_by",
            "raised_by_name",
            "resolution_notes",
            "resolved_by",
            "resolved_by_name",
            "resolved_at",
            "created_at",
        )
        read_only_fields = fields


class DiscrepancyCreateSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=Discrepancy.Kind.choices)
    direction = serializers.ChoiceField(
        choices=Discrepancy.Direction.choices,
        required=False,
        help_text="Implied by the kind for cash discrepancies; required otherwise.",
    )
    amount = MoneyField()
    reason_code = serializers.ChoiceField(choices=Discrepancy.ReasonCode.choices)
    notes = serializers.CharField(max_length=2000)
    submission_id = serializers.IntegerField(
        required=False, min_value=1, help_text="For cash shortage/excess."
    )
    deposit_id = serializers.IntegerField(
        required=False, min_value=1, help_text="For deposit, settlement and gateway mismatches."
    )


class DiscrepancyResolveSerializer(serializers.Serializer):
    outcome = serializers.ChoiceField(
        choices=[
            (Discrepancy.Status.RESOLVED, "Resolved (recovered or explained)"),
            (Discrepancy.Status.WRITTEN_OFF, "Written off"),
        ]
    )
    resolution_notes = serializers.CharField(max_length=2000)


# Summaries


class SummaryQuerySerializer(serializers.Serializer):
    date_from = serializers.DateField(required=False, help_text="Defaults to date_to.")
    date_to = serializers.DateField(required=False, help_text="Defaults to today.")
    branch = serializers.IntegerField(required=False, min_value=1)

    def validate(self, attrs):
        attrs.setdefault("date_to", business_date())
        attrs.setdefault("date_from", attrs["date_to"])
        if attrs["date_from"] > attrs["date_to"]:
            raise serializers.ValidationError({"date_from": "Must be on or before date_to."})
        return attrs


class BranchSummaryMetricsSerializer(serializers.Serializer):
    expected_due = _amount(help_text="Installments falling due in the period.")
    collected_cash = _amount()
    collected_upi = _amount()
    collected_total = _amount()
    held_by_agents = _amount(help_text="Cash still with agents (now).")
    pending_verification = _amount(help_text="Cash submitted and awaiting review (now).")
    pending_submissions = serializers.IntegerField()
    received_at_branch = _amount(help_text="Cash counted on submissions approved in the period.")
    at_branch_not_deposited = _amount(help_text="Approved cash not yet deposited (now).")
    deposited = _amount(help_text="Cash deposits dated in the period, excluding failed ones.")
    pending_settlement = _amount(help_text="Deposits awaiting bank confirmation (now).")
    delayed_deposits = serializers.IntegerField(help_text="Pending beyond the settlement SLA.")
    settled_cash = _amount(help_text="Cash receipts credited in the period, by bank date.")
    settled_upi = _amount(help_text="UPI receipts credited in the period, by bank date.")
    settled_total = _amount()
    open_discrepancies = serializers.IntegerField()
    open_shortage = _amount()
    open_excess = _amount()


class BranchSummaryRowSerializer(BranchSummaryMetricsSerializer):
    branch_id = serializers.IntegerField()
    branch_code = serializers.CharField()
    branch_name = serializers.CharField()


class BranchSummarySerializer(serializers.Serializer):
    date_from = serializers.DateField()
    date_to = serializers.DateField()
    totals = BranchSummaryMetricsSerializer()
    branches = BranchSummaryRowSerializer(many=True)


class AgentSummaryMetricsSerializer(serializers.Serializer):
    collected_cash = _amount()
    collected_upi = _amount()
    collection_count = serializers.IntegerField()
    submitted = _amount(help_text="Cash handed over in the period (rejected hand-overs excluded).")
    received = _amount(help_text="Cash counted on hand-overs approved in the period.")
    cash_in_hand = _amount(help_text="Cash collected but not yet handed over (now).")
    receipts_in_hand = serializers.IntegerField()
    pending_verification = _amount(help_text="Cash handed over and awaiting review (now).")
    held_under_1d = _amount()
    held_1_to_2d = _amount()
    held_over_2d = _amount()
    open_shortage = _amount(help_text="Open cash shortages attributed to the agent.")


class AgentSummaryRowSerializer(AgentSummaryMetricsSerializer):
    agent_id = serializers.IntegerField()
    username = serializers.CharField()
    full_name = serializers.CharField()
    branch_id = serializers.IntegerField(allow_null=True)
    branch_code = serializers.CharField(allow_null=True)
    oldest_held_at = serializers.DateTimeField(allow_null=True)
    oldest_held_hours = serializers.IntegerField(allow_null=True)


class AgentsSummarySerializer(serializers.Serializer):
    date_from = serializers.DateField()
    date_to = serializers.DateField()
    as_of = serializers.DateTimeField()
    totals = AgentSummaryMetricsSerializer()
    agents = AgentSummaryRowSerializer(many=True)
