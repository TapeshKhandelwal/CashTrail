from django.contrib import admin

from apps.core.admin import ReadOnlyAdminMixin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = (
        "created_at",
        "action",
        "entity_type",
        "entity_id",
        "actor",
        "branch",
        "ip_address",
    )
    list_filter = ("action", "entity_type", "branch")
    list_select_related = ("actor", "branch")
    search_fields = ("entity_id", "actor__username", "request_id")
    date_hierarchy = "created_at"
