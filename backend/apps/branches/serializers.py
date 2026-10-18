from rest_framework import serializers

from .models import Branch


class BranchSerializer(serializers.ModelSerializer):
    agent_count = serializers.IntegerField(read_only=True)
    customer_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Branch
        fields = (
            "id",
            "code",
            "name",
            "city",
            "address",
            "is_active",
            "agent_count",
            "customer_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class BranchCreateSerializer(serializers.ModelSerializer):
    # Declared explicitly so uniqueness is checked by the service on the normalized code.
    code = serializers.CharField(max_length=10)

    class Meta:
        model = Branch
        fields = ("code", "name", "city", "address")


class BranchUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = ("name", "city", "address", "is_active")
