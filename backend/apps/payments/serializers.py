from rest_framework import serializers

from apps.collections.serializers import CollectionDetailSerializer
from apps.core.money import MoneyField, money_to_paise

from .models import GatewayOrder, GatewayProvider, WebhookEvent
from .providers.mock import MockOutcome


class GatewayOrderSerializer(serializers.ModelSerializer):
    loan_number = serializers.CharField(source="loan.loan_number")
    customer = serializers.IntegerField(source="loan.customer_id")
    customer_name = serializers.CharField(source="loan.customer.full_name")
    branch = serializers.IntegerField(source="loan.branch_id")
    branch_code = serializers.CharField(source="loan.branch.code")
    agent_name = serializers.CharField(source="agent.get_full_name")
    amount = MoneyField()
    amount_paise = serializers.SerializerMethodField()
    receipt_number = serializers.CharField(source="collection.receipt_number", allow_null=True)
    expires_at = serializers.DateTimeField()

    class Meta:
        model = GatewayOrder
        fields = (
            "id",
            "provider",
            "provider_order_id",
            "receipt",
            "loan",
            "loan_number",
            "customer",
            "customer_name",
            "branch",
            "branch_code",
            "agent",
            "agent_name",
            "amount",
            "amount_paise",
            "status",
            "provider_payment_id",
            "collection",
            "receipt_number",
            "paid_at",
            "failed_at",
            "failure_reason",
            "created_at",
            "expires_at",
        )
        read_only_fields = fields

    @staticmethod
    def get_amount_paise(obj) -> int:
        return money_to_paise(obj.amount)


class OrderCreateSerializer(serializers.Serializer):
    loan_id = serializers.IntegerField(min_value=1)
    amount = MoneyField()


class GatewayConfigSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(choices=GatewayProvider.choices)
    key_id = serializers.CharField(
        help_text="Public checkout key (Razorpay); empty for Cashfree and the mock gateway."
    )
    environment = serializers.CharField(
        help_text="What the checkout runs against: `test`/`live` (Razorpay, mock) or "
        "`sandbox`/`production` (Cashfree)."
    )
    currency = serializers.CharField()
    checkout_script = serializers.CharField(help_text="Empty for the mock gateway.")
    checkout_timeout_seconds = serializers.IntegerField()


class PrefillSerializer(serializers.Serializer):
    name = serializers.CharField()
    contact = serializers.CharField()
    email = serializers.CharField()


class CheckoutSerializer(GatewayConfigSerializer):
    order_id = serializers.CharField()
    session_id = serializers.CharField(
        help_text="Payment session the Cashfree checkout opens with; empty for other gateways."
    )
    amount = MoneyField()
    amount_paise = serializers.IntegerField()
    description = serializers.CharField()
    expires_at = serializers.DateTimeField()
    prefill = PrefillSerializer()
    notes = serializers.DictField(child=serializers.CharField())


class OrderCreatedSerializer(serializers.Serializer):
    order = GatewayOrderSerializer()
    checkout = CheckoutSerializer()


class VerifyPaymentSerializer(serializers.Serializer):
    order_id = serializers.CharField(max_length=64, help_text="Gateway order id.")
    payment_id = serializers.CharField(max_length=64)
    signature = serializers.CharField(max_length=128)


class MockPaySerializer(serializers.Serializer):
    outcome = serializers.ChoiceField(choices=MockOutcome.choices, default=MockOutcome.SUCCESS)


class PaymentResultSerializer(serializers.Serializer):
    order = GatewayOrderSerializer()
    receipt = CollectionDetailSerializer(allow_null=True)
    payment_in_progress = serializers.BooleanField(
        help_text="An attempt is still undecided at the gateway (status checks only); the "
        "order may yet be paid even if an earlier attempt failed."
    )


class WebhookAckSerializer(serializers.Serializer):
    event_id = serializers.CharField()
    status = serializers.ChoiceField(choices=["processed", "duplicate", "failed"])


class WebhookEventSerializer(serializers.ModelSerializer):
    order_id = serializers.CharField(allow_null=True, help_text="Gateway order id in the event.")
    payment_id = serializers.CharField(allow_null=True)

    class Meta:
        model = WebhookEvent
        fields = (
            "id",
            "provider",
            "event_id",
            "event_type",
            "order_id",
            "payment_id",
            "processed_at",
            "error",
            "payload",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields
