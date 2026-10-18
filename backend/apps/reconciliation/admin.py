from django.contrib import admin

from apps.core.admin import ReadOnlyAdminMixin

from .models import CashSubmission, Discrepancy


@admin.register(CashSubmission)
class CashSubmissionAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = (
        "submission_number",
        "agent",
        "branch",
        "expected_amount",
        "received_amount",
        "difference",
        "status",
        "submitted_at",
    )
    list_filter = ("status", "branch")
    list_select_related = ("agent", "branch")
    search_fields = ("submission_number", "agent__username")
    date_hierarchy = "submitted_at"


@admin.register(Discrepancy)
class DiscrepancyAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "kind",
        "amount",
        "branch",
        "agent",
        "status",
        "reason_code",
        "created_at",
    )
    list_filter = ("status", "kind", "reason_code", "branch")
    list_select_related = ("branch", "agent")
    date_hierarchy = "created_at"
