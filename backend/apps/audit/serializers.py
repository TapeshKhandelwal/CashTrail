from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.customers.serializers import hides_contact_details, mask_phone

from . import selectors
from .models import AuditAction, AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    action_label = serializers.SerializerMethodField()
    entity_label = serializers.SerializerMethodField()
    entity_reference = serializers.SerializerMethodField()
    actor_username = serializers.CharField(source="actor.username", read_only=True, default=None)
    actor_name = serializers.CharField(source="actor.get_full_name", read_only=True, default=None)
    branch_code = serializers.CharField(source="branch.code", read_only=True, default=None)
    before = serializers.JSONField(read_only=True)
    after = serializers.JSONField(read_only=True)

    class Meta:
        model = AuditLog
        fields = (
            "id",
            "created_at",
            "action",
            "action_label",
            "entity_type",
            "entity_id",
            "entity_label",
            "entity_reference",
            "actor",
            "actor_username",
            "actor_name",
            "branch",
            "branch_code",
            "before",
            "after",
            "ip_address",
            "user_agent",
            "request_id",
        )
        read_only_fields = fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.entity_type == "customer" and hides_contact_details(
            self.context.get("request")
        ):
            for side in ("before", "after"):
                if data[side] and data[side].get("phone"):
                    data[side] = {**data[side], "phone": mask_phone(data[side]["phone"])}
        return data

    @extend_schema_field(OpenApiTypes.STR)
    def get_action_label(self, entry: AuditLog) -> str:
        try:
            return AuditAction(entry.action).label
        except ValueError:
            return entry.action

    @extend_schema_field(OpenApiTypes.STR)
    def get_entity_label(self, entry: AuditLog) -> str:
        return selectors.entity_label(entry.entity_type)

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_entity_reference(self, entry: AuditLog) -> str | None:
        """The record's document number (receipt, hand-over, deposit...), when it has one."""
        references = self.context.get("entity_references")
        if references is None:
            references = selectors.entity_references([entry])
        return references.get((entry.entity_type, entry.entity_id))
