from django.contrib import admin

from apps.core.admin import ReadOnlyAdminMixin

from .models import Allocation, Collection


class AllocationInline(ReadOnlyAdminMixin, admin.TabularInline):
    model = Allocation
    fields = ("installment", "amount", "reversed_at")
    readonly_fields = fields
    extra = 0


@admin.register(Collection)
class CollectionAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = (
        "receipt_number",
        "loan",
        "agent",
        "branch",
        "amount",
        "mode",
        "status",
        "collected_at",
    )
    list_filter = ("status", "mode", "branch")
    list_select_related = ("loan", "agent", "branch")
    search_fields = (
        "receipt_number",
        "loan__loan_number",
        "customer__full_name",
        "gateway_payment_id",
    )
    date_hierarchy = "collected_at"
    inlines = (AllocationInline,)


@admin.register(Allocation)
class AllocationAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("collection", "installment", "amount", "reversed_at")
    list_select_related = ("collection", "installment__loan")
    search_fields = ("collection__receipt_number",)
