from django.contrib import admin

from apps.core.admin import ReadOnlyAdminMixin

from .models import BankAccount, BankDeposit


@admin.register(BankAccount)
class BankAccountAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = (
        "bank_name",
        "account_name",
        "account_number_last4",
        "ifsc",
        "is_gateway",
        "is_active",
    )
    list_filter = ("is_gateway", "is_active")
    search_fields = ("bank_name", "account_name", "ifsc")


@admin.register(BankDeposit)
class BankDepositAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = (
        "deposit_number",
        "source",
        "branch",
        "bank_account",
        "reference_number",
        "deposit_date",
        "deposited_amount",
        "settled_amount",
        "status",
    )
    list_filter = ("status", "source", "branch", "bank_account")
    list_select_related = ("branch", "bank_account")
    search_fields = ("deposit_number", "reference_number", "settlement_reference")
    date_hierarchy = "deposit_date"
