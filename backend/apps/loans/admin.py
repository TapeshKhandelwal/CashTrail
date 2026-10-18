from django.contrib import admin

from apps.core.admin import ReadOnlyAdminMixin

from .models import Installment, Loan


class InstallmentInline(ReadOnlyAdminMixin, admin.TabularInline):
    model = Installment
    fields = ("installment_no", "due_date", "amount_due", "amount_paid", "status", "paid_at")
    readonly_fields = fields
    extra = 0


@admin.register(Loan)
class LoanAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = (
        "loan_number",
        "customer",
        "branch",
        "principal",
        "total_payable",
        "amount_paid",
        "status",
        "disbursed_on",
    )
    list_filter = ("status", "branch")
    list_select_related = ("customer", "branch")
    search_fields = ("loan_number", "customer__full_name", "customer__customer_code")
    date_hierarchy = "disbursed_on"
    inlines = (InstallmentInline,)


@admin.register(Installment)
class InstallmentAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("loan", "installment_no", "due_date", "amount_due", "amount_paid", "status")
    list_filter = ("status",)
    list_select_related = ("loan",)
    search_fields = ("loan__loan_number",)
    date_hierarchy = "due_date"
